"""
production_reports_to_s3 -- copies the hourly `Production Report` events (written by hourly_production_report,
corrected by shift_reconciler, incidents added by plant_incident_sync) to S3 as one JSON Lines file per machine and
shift, so Amazon Athena can query them with SQL and Amazon Managed Grafana can chart and download them.

    s3://ingedaca-polar-production-data/production_hourly/shift_date=2026-11-19/shift=day/standum32.jsonl

Each line is one hour of one machine (columns in README.md). Every file is rewritten whole from the shift's events,
so a corrected hour or a new incident replaces the old row; a file is only uploaded when its content changed (the
bucket has versioning on).

`data` (all optional):
    dry_run    bool, default False: build everything, upload nothing; the result lists the files and a sample row.
    from, to   "YYYY-MM-DD" shift dates, both inclusive: BACKFILL every shift in that range (initial load).
               Without them: the shifts of the events created/updated in the last `lookback_hours`.
    lookback_hours  default LOOKBACK_HOURS (3).
    machines   list of machine codes (e.g. ["standum32"]) to limit the run to.

AWS credentials: Fusion Function secrets `aws-access-key` / `aws-secret-key` (same names as shift-excel-report-v2).
Locally, boto3's default chain (the AWS CLI profile) is used.
"""
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import boto3
from botocore.exceptions import ClientError

from config import AWS_REGION, BUCKET, EVENT_TYPE, LOCAL_TZ, LOOKBACK_HOURS, MACHINES, NUMERIC_FIELDS, PREFIX

EXT_ID = re.compile(r"^report_(?P<code>.+)_(?P<date>\d{8})_(?P<shift>day|night)_entry_(?P<slot>\d+)$")


def _num(meta, keys):
    """First of `keys` in the metadata as a number (handles "12.5%"); None if absent or not a number."""
    lower = {str(k).lower(): v for k, v in meta.items()}
    for k in keys:
        v = lower.get(k.lower())
        if v is None or str(v).strip() == "":
            continue
        try:
            return float(str(v).replace("%", "").strip())
        except ValueError:
            continue
    return None


def _hour_label(h):
    """6 -> "6AM-7AM", 12 -> "12PM-1PM", 23 -> "11PM-12AM" (as the Reporte shows them)."""
    fmt = lambda x: f"{(x % 12) or 12}{'AM' if x % 24 < 12 else 'PM'}"
    return f"{fmt(h)}-{fmt(h + 1)}"


def event_to_row(evt):
    """One output row from one Production Report event, or None if it isn't one of the 32 machines' hourly reports."""
    m = EXT_ID.match(evt.external_id or "")
    if not m or m.group("code").lower() not in MACHINES or evt.start_time is None:
        return None
    code = m.group("code").lower()
    line, mtype = MACHINES[code]
    meta = dict(evt.metadata or {})
    start_utc = datetime.fromtimestamp(evt.start_time / 1000, timezone.utc)
    start_local = start_utc.astimezone(LOCAL_TZ)
    d = m.group("date")
    row = {
        "hour_start_utc": start_utc.strftime("%Y-%m-%d %H:%M:%S"),        # Grafana time axis / $__timeFilter
        "hour_start_local": start_local.strftime("%Y-%m-%d %H:%M:%S"),    # plant time, for the downloaded data
        "hour_label": _hour_label(start_local.hour),
        "slot": int(m.group("slot")),
        "line": line,
        "machine_type": mtype,
        "machine": code,
    }
    for col, keys in NUMERIC_FIELDS.items():
        row[col] = _num(meta, keys)
    obs = meta.get("observations", meta.get("observaciones"))
    row["observations"] = None if obs is None else str(obs)
    code_str = meta.get("incident_code")
    row["incident_code"] = int(code_str) if code_str not in (None, "") and str(code_str).lstrip("-").isdigit() else None
    row["incident_source"] = meta.get("incident_source")
    row["event_external_id"] = evt.external_id
    row["event_last_updated_utc"] = (datetime.fromtimestamp(evt.last_updated_time / 1000, timezone.utc)
                                     .strftime("%Y-%m-%d %H:%M:%S") if evt.last_updated_time else None)
    key = (code, f"{d[:4]}-{d[4:6]}-{d[6:]}", m.group("shift"))
    return key, row


def s3_key(code, shift_date, shift):
    return f"{PREFIX}/shift_date={shift_date}/shift={shift}/{code}.jsonl"


def shift_file(rows):
    """JSON Lines body for one machine-shift: rows sorted by slot, one per hour."""
    rows = sorted(rows, key=lambda r: r["slot"])
    return "".join(json.dumps(r, ensure_ascii=False, sort_keys=False) + "\n" for r in rows).encode("utf-8")


def _shift_ext_ids(code, shift_date, shift):
    d = shift_date.replace("-", "")
    return [f"report_{code}_{d}_{shift}_entry_{s:02d}" for s in range(1, 13)]


def collect(client, data):
    """{(code, shift_date, shift): [rows]} for the shifts this run must (re)write."""
    wanted = {m.lower() for m in data.get("machines") or []} or None
    files = defaultdict(list)
    if data.get("from") or data.get("to"):
        # backfill: every event whose shift date is in [from, to]; a night shift ends at 06:00 the next day
        d0 = datetime.strptime(data.get("from") or data["to"], "%Y-%m-%d").replace(hour=6, tzinfo=LOCAL_TZ)
        d1 = datetime.strptime(data.get("to") or data["from"], "%Y-%m-%d").replace(hour=6, tzinfo=LOCAL_TZ) \
            + timedelta(days=1)
        evs = client.events.list(type=EVENT_TYPE, start_time={"min": int(d0.timestamp() * 1000),
                                                              "max": int(d1.timestamp() * 1000) - 1}, limit=None)
        for e in evs:
            got = event_to_row(e)
            if got and (wanted is None or got[0][0] in wanted):
                files[got[0]].append(got[1])
        return files
    # incremental: shifts of the events touched recently, then ALL hours of those shifts (a whole file is rewritten)
    since = datetime.now(timezone.utc) - timedelta(hours=float(data.get("lookback_hours", LOOKBACK_HOURS)))
    touched = set()
    for e in client.events.list(type=EVENT_TYPE, last_updated_time={"min": int(since.timestamp() * 1000)}, limit=None):
        got = event_to_row(e)
        if got and (wanted is None or got[0][0] in wanted):
            touched.add(got[0])
    if touched:
        ids = [x for k in touched for x in _shift_ext_ids(*k)]
        for i in range(0, len(ids), 1000):
            for e in client.events.retrieve_multiple(external_ids=ids[i:i + 1000], ignore_unknown_ids=True):
                got = event_to_row(e)
                if got and got[0] in touched:
                    files[got[0]].append(got[1])
    return files


def _s3(secrets):
    secrets = secrets or {}
    key = (secrets.get("aws-access-key") or "").strip() or None
    secret = (secrets.get("aws-secret-key") or "").strip() or None
    if key and secret:
        return boto3.client("s3", region_name=AWS_REGION, aws_access_key_id=key, aws_secret_access_key=secret)
    return boto3.client("s3", region_name=AWS_REGION)


def _unchanged(s3, key, body):
    """True when S3 already holds exactly this body (single-part SSE-S3 upload: ETag = MD5 of the content)."""
    try:
        etag = s3.head_object(Bucket=BUCKET, Key=key)["ETag"].strip('"')
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
            return False
        raise
    return etag == hashlib.md5(body).hexdigest()


def handle(client=None, data=None, secrets=None):  # noqa: D401 - CDF Functions entry point
    data = data or {}
    dry_run = bool(data.get("dry_run", False))
    files = collect(client, data)
    result = {"dry_run": dry_run, "bucket": BUCKET, "files": len(files), "rows": sum(len(r) for r in files.values()),
              "uploaded": 0, "unchanged": 0, "errors": []}
    if dry_run:
        keys = sorted(s3_key(*k) for k in files)
        result["keys"] = keys[:50] + ([f"... {len(keys) - 50} more"] if len(keys) > 50 else [])
        if files:
            k0 = sorted(files)[0]
            result["sample_row"] = sorted(files[k0], key=lambda r: r["slot"])[0]
        print(json.dumps({k: v for k, v in result.items() if k not in ("keys", "sample_row")}))
        return result
    s3 = _s3(secrets)
    for k, rows in sorted(files.items()):
        key, body = s3_key(*k), shift_file(rows)
        try:
            if _unchanged(s3, key, body):
                result["unchanged"] += 1
                continue
            s3.put_object(Bucket=BUCKET, Key=key, Body=body, ContentType="application/x-ndjson; charset=utf-8")
            result["uploaded"] += 1
        except Exception as e:                       # keep going: the next run retries this file
            result["errors"].append(f"{key}: {type(e).__name__}: {e}")
    print(json.dumps(result))
    return result
