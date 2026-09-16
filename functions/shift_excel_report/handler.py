"""
Shift Excel report -- Cognite Function.

Keeps "Short Can - D&I y STD.xlsx" (stored in CDF Files as
config.FILE_EXTERNAL_ID) up to date: each run, it fills in the most
recently completed shift's D&I/Standum production, short-can, and
trimmer-jam totals (computed from the same hourly Production Report events
hourly_production_report writes), and tops up the file's blank-row
scaffold so there's always a buffer of future rows ready to be filled.

Local development / testing: see local_test.py. Like
hourly_production_report, `dry_run` (default False passed in `data`) skips
the final re-upload to CDF Files -- everything is computed from real CDF
reads, but nothing is written back until dry_run is explicitly turned off.
"""
import copy
import io
from datetime import datetime, timedelta
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import boto3
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from config import (
    ATTACHMENT_NAME,
    AWS_REGION,
    DATA_SET_ID,
    DI15_INTRODUCED_DATE,
    DI_MACHINES,
    EMAIL_FROM,
    EMAIL_TO,
    FILE_EXTERNAL_ID,
    LOCAL_TZ,
    MACHINE_MAP,
    SCAFFOLD_BUFFER_DAYS,
    SHIFT_CODE_TO_TURNO,
    STANDUN_MACHINES,
    TURNO_TO_SHIFT_CODE,
    _PRODUCTION_KEYS,
    _SHORT_CAN_KEYS,
    _TRIMMER_JAM_KEYS,
)

SHEET_CONFIG = {
    "STANDUN": {
        "machines": STANDUN_MACHINES,
        "table": "Tabla1",
        "day_col_formula": True,  # Semana/Dia/Mes are live formulas on this sheet's tail rows
    },
    "D&I": {
        "machines": DI_MACHINES,
        "table": "Tabla14",
        "day_col_formula": False,  # this sheet's tail rows use static values instead
    },
}


def _meta_num(meta: dict, keys: list) -> float:
    meta_lower = {str(k).lower(): v for k, v in meta.items()}
    for k in keys:
        kl = k.lower()
        if kl in meta_lower and meta_lower[kl] is not None:
            try:
                return float(str(meta_lower[kl]).replace("%", "").strip())
            except (ValueError, TypeError):
                continue
    return 0.0


def _last_completed_shift(now_local: datetime) -> dict:
    """
    Which shift most recently ended, relative to now. Day: 06:00-18:00,
    filed under that same date. Night: 18:00-06:00, filed under the date it
    STARTED. Mirrors hourly_production_report's _shift_context() date/shift
    convention, but at shift granularity instead of hour granularity.
    """
    hour = now_local.hour
    if 6 <= hour < 18:
        # Currently in the day shift -> the last completed shift was last
        # night's, which started (and is filed under) yesterday.
        shift_code = "night"
        shift_date = (now_local - timedelta(days=1)).date()
    else:
        # Currently in the night shift -> the last completed shift was
        # today's day shift, unless it's still the small hours (<06:00), in
        # which case "today" for the day shift that just ended is actually
        # yesterday's calendar date.
        shift_code = "day"
        shift_date = now_local.date() if hour >= 18 else (now_local - timedelta(days=1)).date()
    return {
        "shift_code": shift_code,
        "turno": SHIFT_CODE_TO_TURNO[shift_code],
        "fecha": shift_date,
        "date_str": shift_date.strftime("%Y%m%d"),
    }


def _shift_totals(client, code: str, date_str: str, shift_code: str) -> tuple:
    ext_ids = [f"report_{code}_{date_str}_{shift_code}_entry_{slot:02d}" for slot in range(1, 13)]
    events = client.events.retrieve_multiple(external_ids=ext_ids, ignore_unknown_ids=True)
    prod, sc, tj = 0.0, 0.0, 0.0
    for e in events:
        meta = e.metadata or {}
        prod += _meta_num(meta, _PRODUCTION_KEYS)
        sc += _meta_num(meta, _SHORT_CAN_KEYS)
        tj += _meta_num(meta, _TRIMMER_JAM_KEYS)
    return prod, sc, tj


def _download_workbook(client):
    content = client.files.download_bytes(external_id=FILE_EXTERNAL_ID)
    return load_workbook(io.BytesIO(content))


def _col_index(header: list, *, exact: str = None, contains: str = None) -> int:
    for i, h in enumerate(header):
        if h is None:
            continue
        if exact is not None and h == exact:
            return i + 1
        if contains is not None and contains in h:
            return i + 1
    raise ValueError(f"Column not found (exact={exact!r}, contains={contains!r}) in header={header!r}")


def _fill_shift_blanks(client, wb, fecha_date, turno: str, shift_code: str, date_str: str, force: bool = False) -> dict:
    """
    Fills the 3 data columns for every row matching (FECHA, TURNO) whose
    MAQUINA maps to a real CDF machine code AND whose cells are currently
    blank (idempotent by default -- a re-run never clobbers an already-
    filled cell). force=True overwrites already-filled cells too, for
    re-running a shift after shift_reconciler has corrected its underlying
    hourly events (e.g. a machine caught mid-backfill after an outage).
    """
    filled = {}
    for sheet_name in SHEET_CONFIG:
        ws = wb[sheet_name]
        header = [c.value for c in ws[1]]
        fecha_col = _col_index(header, exact="FECHA")
        turno_col = _col_index(header, exact="TURNO")
        maquina_col = _col_index(header, contains="QUINA")
        prod_col = _col_index(header, contains="PROD")
        sc_col = _col_index(header, exact="SHORT CAN")
        tj_col = _col_index(header, contains="TRANCAMIENTO")

        for row in ws.iter_rows(min_row=2):
            fecha = row[fecha_col - 1].value
            if fecha is None or row[turno_col - 1].value != turno:
                continue
            if fecha.date() != fecha_date:
                continue
            maquina = row[maquina_col - 1].value
            code = MACHINE_MAP.get(maquina)
            if code is None:
                continue
            if row[prod_col - 1].value is not None and not force:
                continue  # already filled, don't overwrite
            prod, sc, tj = _shift_totals(client, code, date_str, shift_code)
            row[prod_col - 1].value = prod
            row[sc_col - 1].value = sc
            row[tj_col - 1].value = tj
            filled[f"{sheet_name}:{maquina}"] = {"production": prod, "short_cans": sc, "trimmer_jams": tj}
    return filled


def _ensure_di15_rows(wb, min_fecha) -> int:
    """
    Safety net: inserts a blank D&I-15 row right after D&I-14 for any
    (FECHA, TURNO) group ON OR AFTER min_fecha that doesn't already have
    one. Idempotent -- a group that already has D&I-15 is left alone.
    Needed because _extend_scaffold already includes D&I-15 in new rows it
    creates, but this guards against any row group that predates that (or
    was created by some other process) missing it.

    min_fecha matters a lot here: D&I-15 was deliberately added only GOING
    FORWARD (explicit instruction, not retroactive) -- historical groups
    before that point never had it and must stay that way. Without this
    floor, this function would try to backfill it into every one of the
    ~570 historical (FECHA, TURNO) groups that predate D&I-15's addition.
    """
    ws = wb["D&I"]
    header = [c.value for c in ws[1]]
    fecha_col = _col_index(header, exact="FECHA")
    turno_col = _col_index(header, exact="TURNO")
    maquina_col = _col_index(header, contains="QUINA")

    groups_seen = {}
    for row in ws.iter_rows(min_row=2):
        fecha = row[fecha_col - 1].value
        if fecha is None:
            continue
        key = (fecha.date(), row[turno_col - 1].value)
        maquina = row[maquina_col - 1].value
        groups_seen.setdefault(key, {})[maquina] = row[0].row

    inserted = 0
    # Process bottom-to-top so earlier row numbers stay valid as we insert.
    missing = [
        (key, rows) for key, rows in groups_seen.items()
        if "D&I-14" in rows and "D&I-15" not in rows and key[0] >= min_fecha
    ]
    missing.sort(key=lambda kv: kv[1]["D&I-14"], reverse=True)
    for (fecha_d, turno), rows in missing:
        d14_row = rows["D&I-14"]
        new_row_idx = d14_row + 1
        ws.insert_rows(new_row_idx, amount=1)
        src_row = ws[d14_row]
        dst_row = ws[new_row_idx]
        for col_idx in range(1, len(header) + 1):
            src_cell = src_row[col_idx - 1]
            dst_cell = dst_row[col_idx - 1]
            dst_cell._style = copy.copy(src_cell._style)
            if col_idx == maquina_col:
                dst_cell.value = "D&I-15"
            elif col_idx in (fecha_col, turno_col):
                dst_cell.value = src_cell.value
            else:
                header_name = header[col_idx - 1]
                if header_name in ("DIA", "SEMANA"):
                    dst_cell.value = src_cell.value
        inserted += 1

    if inserted:
        ws.tables["Tabla14"].ref = f"A1:H{ws.max_row}"
    return inserted


def _extend_scaffold(wb, through_date) -> dict:
    """
    Appends new blank-scaffold rows (FECHA/TURNO/MAQUINA filled, data
    columns blank) so both sheets have rows through `through_date`
    inclusive, for every machine in that sheet's full roster (including
    D&I-15 in its proper position). Mirrors each sheet's own existing
    convention for DIA/SEMANA/Mes on new rows: STANDUN's tail already uses
    live formulas, so new STANDUN rows get the same formulas; D&I's tail
    uses static values, so new D&I rows get static values too.
    """
    added = {}
    for sheet_name, cfg in SHEET_CONFIG.items():
        ws = wb[sheet_name]
        header = [c.value for c in ws[1]]
        fecha_col = _col_index(header, exact="FECHA")
        turno_col = _col_index(header, exact="TURNO")
        maquina_col = _col_index(header, contains="QUINA")

        # The Table's own column count, NOT len(header) -- some sheets (D&I)
        # have stray unnamed/empty trailing columns beyond the Table's real
        # range that would otherwise get folded into an over-wide new ref.
        orig_n_cols = len(ws.tables[cfg["table"]].tableColumns)

        last_fecha = None
        last_row_by_key = {}
        for row in ws.iter_rows(min_row=2):
            fecha = row[fecha_col - 1].value
            if fecha is None:
                continue
            if last_fecha is None or fecha.date() > last_fecha:
                last_fecha = fecha.date()
            last_row_by_key[(fecha.date(), row[turno_col - 1].value, row[maquina_col - 1].value)] = row

        if last_fecha is None or last_fecha >= through_date:
            added[sheet_name] = 0
            continue

        # A template row to copy styling from -- any existing row will do.
        template_row = ws[ws.max_row]

        n_added = 0
        d = last_fecha + timedelta(days=1)
        while d <= through_date:
            for turno in ("1ER", "2DO"):
                for maquina in cfg["machines"]:
                    new_row_idx = ws.max_row + 1
                    for col_idx in range(1, len(header) + 1):
                        src_cell = template_row[col_idx - 1]
                        dst_cell = ws.cell(row=new_row_idx, column=col_idx)
                        dst_cell._style = copy.copy(src_cell._style)
                    header_name_by_col = {i + 1: h for i, h in enumerate(header)}
                    for col_idx, header_name in header_name_by_col.items():
                        cell = ws.cell(row=new_row_idx, column=col_idx)
                        if header_name == "FECHA":
                            cell.value = datetime(d.year, d.month, d.day)
                        elif header_name == "TURNO":
                            cell.value = turno
                        elif header_name and "QUINA" in header_name:
                            cell.value = maquina
                        elif header_name in ("DIA", "Dia"):
                            table_name = cfg["table"]
                            cell.value = f"=DAY({table_name}[[#This Row],[FECHA]])" if cfg["day_col_formula"] else d.day
                        elif header_name in ("SEMANA", "Semana"):
                            table_name = cfg["table"]
                            cell.value = f"=WEEKNUM({table_name}[[#This Row],[FECHA]])" if cfg["day_col_formula"] else d.isocalendar()[1]
                        elif header_name == "Mes":
                            cell.value = f'=+TEXT({cfg["table"]}[],"mmmm")' if cfg["day_col_formula"] else d.strftime("%B")
                    n_added += 1
            d += timedelta(days=1)

        if n_added:
            tbl = ws.tables[cfg["table"]]
            last_col_letter = get_column_letter(orig_n_cols)
            tbl.ref = f"A1:{last_col_letter}{ws.max_row}"
        added[sheet_name] = n_added

    return added


def _upload_workbook(client, wb) -> bytes:
    buf = io.BytesIO()
    wb.save(buf)
    content = buf.getvalue()
    client.files.upload_bytes(
        content=content,
        name="short_can_report.xlsx",
        external_id=FILE_EXTERNAL_ID,
        data_set_id=DATA_SET_ID,
        overwrite=True,
    )
    return content


def _send_report_email(content: bytes, ctx: dict, secrets: dict = None) -> str:
    """
    secrets carries AWS credentials when running as a deployed CDF Function
    -- that sandbox has no ~/.aws/credentials file for boto3's default
    credential chain to find, unlike a local run authenticated via the AWS
    CLI. If secrets has aws_access_key_id/aws_secret_access_key (configured
    on the Function itself in Fusion, see README), boto3 is built with them
    explicitly; otherwise it falls back to the default chain, which is what
    makes local testing work with zero extra setup.
    """
    turno_label = "1er turno (dia)" if ctx["shift_code"] == "day" else "2do turno (noche)"
    fecha_label = ctx["fecha"].strftime("%d/%m/%Y")

    msg = MIMEMultipart()
    msg["Subject"] = f"Short Can - D&I y STD - {fecha_label} {turno_label}"
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg.attach(MIMEText(
        f"Adjunto el reporte de produccion actualizado (D&I y Standum) "
        f"para el turno del {fecha_label} ({turno_label}).",
        "plain",
    ))
    part = MIMEApplication(content, Name=ATTACHMENT_NAME)
    part["Content-Disposition"] = f'attachment; filename="{ATTACHMENT_NAME}"'
    msg.attach(part)

    # Fusion's Secrets UI caps keys at 15 chars and only allows lowercase
    # letters, digits, and dashes -- ruling out boto3's own
    # aws_access_key_id/aws_secret_access_key names (too long, underscores).
    secrets = secrets or {}
    # .strip() guards against stray whitespace/newlines from a copy-paste
    # into Fusion's secret value field -- AWS's signature check fails
    # (SignatureDoesNotMatch) on a secret key with even one extra character.
    aws_key = (secrets.get("aws-access-key") or "").strip() or None
    aws_secret = (secrets.get("aws-secret-key") or "").strip() or None
    if aws_key and aws_secret:
        ses = boto3.client("ses", region_name=AWS_REGION, aws_access_key_id=aws_key, aws_secret_access_key=aws_secret)
    else:
        ses = boto3.client("ses", region_name=AWS_REGION)

    response = ses.send_raw_email(
        Source=EMAIL_FROM,
        Destinations=[EMAIL_TO],
        RawMessage={"Data": msg.as_bytes()},
    )
    return response["MessageId"]


def handle(client, data: dict = None, secrets: dict = None) -> dict:  # noqa: F821 - injected by CDF at runtime
    data = data or {}
    dry_run = bool(data.get("dry_run", False))
    force = bool(data.get("force", False))

    now_local = datetime.now(LOCAL_TZ)
    override_date_str = data.get("date_str")
    override_turno = data.get("turno")
    if override_date_str and override_turno:
        shift_date = datetime.strptime(override_date_str, "%Y%m%d").date()
        shift_code = TURNO_TO_SHIFT_CODE[override_turno]
        ctx = {"shift_code": shift_code, "turno": override_turno, "fecha": shift_date, "date_str": override_date_str}
    else:
        ctx = _last_completed_shift(now_local)

    wb = _download_workbook(client)

    filled = _fill_shift_blanks(client, wb, ctx["fecha"], ctx["turno"], ctx["shift_code"], ctx["date_str"], force=force)
    di15_inserted = _ensure_di15_rows(wb, DI15_INTRODUCED_DATE)
    through_date = ctx["fecha"] + timedelta(days=SCAFFOLD_BUFFER_DAYS)
    scaffold_added = _extend_scaffold(wb, through_date)

    result = {
        "now_local": now_local.isoformat(),
        "shift_processed": {**ctx, "fecha": ctx["fecha"].isoformat()},
        "cells_filled": filled,
        "di15_rows_inserted": di15_inserted,
        "scaffold_rows_added": scaffold_added,
        "dry_run": dry_run,
        "email_sent": False,
    }

    if not dry_run:
        content = _upload_workbook(client, wb)

        # Only email when this run actually wrote new shift data (or was an
        # explicit force-correction) -- an idempotent no-op re-run (nothing
        # in `filled`) would otherwise re-send the same report on every
        # retry/duplicate schedule trigger. `send_email` in `data` overrides
        # this either way, for a deliberate manual resend or to suppress it.
        should_email = data.get("send_email", bool(filled) or force)
        if should_email:
            message_id = _send_report_email(content, ctx, secrets=secrets)
            result["email_sent"] = True
            result["email_message_id"] = message_id

    return result
