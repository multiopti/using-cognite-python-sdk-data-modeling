import asyncio

import pandas as pd
import streamlit as st

from cdf_auth import get_async_client
from config import (
    DOWNTIME_KEYS,
    EFFICIENCY_KEYS,
    LINES,
    PRODUCTION_KEYS,
    SCRAP_KEYS,
    SHIFT_MAP,
)


@st.cache_resource
def get_cognite_client():
    return get_async_client()


client = get_cognite_client()


def get_meta_num(meta: dict, keys: list, default: float = 0.0) -> float:
    """First matching key wins -- for fields where only one alias is ever
    present on a given event (production, efficiency, downtime)."""
    meta_lower = {str(k).lower(): v for k, v in meta.items()}
    for k in keys:
        k_lower = k.lower()
        if k_lower in meta_lower and meta_lower[k_lower] is not None:
            try:
                val_str = str(meta_lower[k_lower]).replace("%", "").strip()
                return float(val_str)
            except (ValueError, TypeError):
                continue
    return default


def sum_meta_num(meta: dict, keys: list) -> float:
    """Sums every matching key -- for scrap counters, where a single event
    (Standum/D&I) can carry more than one of these at once."""
    meta_lower = {str(k).lower(): v for k, v in meta.items()}
    total = 0.0
    for k in keys:
        k_lower = k.lower()
        if k_lower in meta_lower and meta_lower[k_lower] is not None:
            try:
                total += float(str(meta_lower[k_lower]).replace("%", "").strip())
            except (ValueError, TypeError):
                continue
    return total


def get_meta_str(meta: dict, keys: list, default: str = "") -> str:
    meta_lower = {str(k).lower(): v for k, v in meta.items()}
    for k in keys:
        k_lower = k.lower()
        if k_lower in meta_lower and meta_lower[k_lower] is not None:
            return str(meta_lower[k_lower])
    return default


async def _load_machine_events(code: str, line: str, m_type: str, fecha_clean: str, shift_code: str) -> list[dict]:
    prefix = f"report_{code.lower()}_{fecha_clean}_{shift_code}"
    events = await client.events.list(type="Production Report", external_id_prefix=prefix, limit=100)
    if not events:
        events = await client.events.list(external_id_prefix=prefix, limit=100)

    rows = []
    for evt in events:
        meta = getattr(evt, "metadata", None) or {}
        ext_id = getattr(evt, "external_id", "") or ""
        try:
            entry_slot = int(ext_id.split("_entry_")[-1])
        except (ValueError, IndexError):
            entry_slot = 0

        rows.append({
            "line": line,
            "machine_type": m_type,
            "machine_code": code,
            "entry_slot": entry_slot,
            "hourly_production": get_meta_num(meta, PRODUCTION_KEYS),
            "pct_eficiencia": get_meta_num(meta, EFFICIENCY_KEYS),
            "downtime_min": get_meta_num(meta, DOWNTIME_KEYS),
            "scrap": sum_meta_num(meta, SCRAP_KEYS),
            "observations": get_meta_str(meta, ["observations"], ""),
        })
    return rows


async def load_overview(fecha_str: str, turno_label: str) -> pd.DataFrame:
    """One row per hourly Production Report event, across every machine in
    both lines, for the given date + shift. Empty DataFrame if nothing was
    found (e.g. a future date, or a shift that hasn't produced any events
    yet)."""
    fecha_clean = fecha_str.replace("-", "")
    shift_code = SHIFT_MAP.get(turno_label, "day")

    tasks = []
    for line, groups in LINES.items():
        for m_type, codes in groups.items():
            for code in codes:
                tasks.append(_load_machine_events(code, line, m_type, fecha_clean, shift_code))

    results = await asyncio.gather(*tasks)
    rows = [row for machine_rows in results for row in machine_rows]
    return pd.DataFrame(rows)


def all_machine_codes() -> list[tuple[str, str, str]]:
    """(line, machine_type, code) for every configured machine -- used to
    render a status pill even for machines with zero events that shift."""
    out = []
    for line, groups in LINES.items():
        for m_type, codes in groups.items():
            for code in codes:
                out.append((line, m_type, code))
    return out
