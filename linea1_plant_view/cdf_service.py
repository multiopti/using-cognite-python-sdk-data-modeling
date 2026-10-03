import asyncio

import streamlit as st

from cdf_auth import get_async_client
from config import ELEMENTS, MINSTER_TARGET, current_shift_key


@st.cache_resource
def get_cognite_client():
    return get_async_client()


client = get_cognite_client()


async def load_line1_values() -> dict:
    """
    Latest value of each LINE1_*_SHIFT rollup timeseries referenced in
    config.ELEMENTS plus MINSTER_TARGET, keyed by external_id.
    hourly_production_report recomputes and re-inserts a fresh datapoint on
    these once per hour (see _write_line_type_rollups in
    functions/hourly_production_report/handler.py), so "latest" is
    effectively "this shift so far".

    A target missing entirely (e.g. renamed/deleted upstream) is dropped
    rather than raising, so one bad external_id doesn't blank the whole
    dashboard -- main.py falls back to "--" for that element.
    """
    ext_ids = [el["target"] for el in ELEMENTS] + [MINSTER_TARGET]
    result = await client.time_series.data.retrieve_latest(external_id=ext_ids, ignore_unknown_ids=True)

    values = {}
    for item in result:
        dps = item.dump().get("datapoints") or []
        if dps:
            values[item.external_id] = dps[0]["value"]
    return values


# --- Per-machine shift totals (D&I, ISPRAY) -------------------------------
# hourly_production_report only writes LINE-level rollups (e.g.
# LINE1_DI_PRODUCTION_SHIFT), not one per physical machine, so per-machine
# numbers are computed here by summing this shift's Production Report events
# directly -- same approach as overview_dashboard/cdf_service.py's
# load_overview(), just narrowed to the machine codes passed in.
_PRODUCTION_KEYS = ["hourly_production", "golpes_bobina_hora"]
_SCRAP_KEYS = ["short_cans_per_hour", "trimmer_jams_per_hour", "hourly_retrac", "blow_off"]


def _meta_num(meta: dict, keys: list) -> float:
    meta_lower = {str(k).lower(): v for k, v in meta.items()}
    for k in keys:
        v = meta_lower.get(k.lower())
        if v is not None:
            try:
                return float(str(v).replace("%", "").strip())
            except (ValueError, TypeError):
                continue
    return 0.0


def _meta_sum(meta: dict, keys: list) -> float:
    meta_lower = {str(k).lower(): v for k, v in meta.items()}
    total = 0.0
    for k in keys:
        v = meta_lower.get(k.lower())
        if v is not None:
            try:
                total += float(str(v).replace("%", "").strip())
            except (ValueError, TypeError):
                continue
    return total


async def _machine_shift_totals(code: str, date_str: str, shift_code: str) -> tuple[float, float]:
    prefix = f"report_{code.lower()}_{date_str}_{shift_code}"
    events = await client.events.list(type="Production Report", external_id_prefix=prefix, limit=100)
    if not events:
        events = await client.events.list(external_id_prefix=prefix, limit=100)

    production = sum(_meta_num(getattr(e, "metadata", None) or {}, _PRODUCTION_KEYS) for e in events)
    scrap = sum(_meta_sum(getattr(e, "metadata", None) or {}, _SCRAP_KEYS) for e in events)
    return production, scrap


async def load_machine_values(codes: list) -> dict:
    """{machine_code: {"production": float, "scrap": float}} for each code
    (e.g. config.DI_MACHINE_CODES, config.ISPRAY_MACHINE_CODES), summed over
    this shift's Production Report events so far. Scrap is always 0 for
    ISPRAY, whose events carry no scrap fields."""
    date_str, shift_code = current_shift_key()
    results = await asyncio.gather(*(_machine_shift_totals(code, date_str, shift_code) for code in codes))
    return {code: {"production": prod, "scrap": scrap} for code, (prod, scrap) in zip(codes, results)}
