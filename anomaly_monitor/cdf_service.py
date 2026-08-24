from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from cdf_auth import get_async_client
from config import DATA_SET_ID

LOCAL_TZ = timezone(timedelta(hours=-4))


@st.cache_resource
def get_cognite_client():
    return get_async_client()


client = get_cognite_client()


def _ms_to_local_str(ms: int) -> str:
    if ms is None:
        return ""
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).astimezone(LOCAL_TZ)
    return dt.strftime("%Y-%m-%d %H:%M")


async def load_anomaly_events(
    days_back: int = 7,
    machine_type: str | None = None,
    machine_code: str | None = None,
    patterns: list[str] | None = None,
    limit: int = 500,
) -> pd.DataFrame:
    """Fetch Data Quality Alert events from CDF and normalize into a
    DataFrame the app can filter/render, most recent first."""
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms = now_ms - days_back * 24 * 60 * 60 * 1000

    events = await client.events.list(
        type="Data Quality Alert",
        data_set_ids=[DATA_SET_ID],
        start_time={"min": start_ms, "max": now_ms},
        limit=limit,
    )

    rows = []
    for e in events:
        meta = getattr(e, "metadata", None) or {}
        row = {
            "external_id": getattr(e, "external_id", ""),
            "pattern": getattr(e, "subtype", None) or meta.get("pattern", "UNKNOWN"),
            "start_time": getattr(e, "start_time", None),
            "start_time_local": _ms_to_local_str(getattr(e, "start_time", None)),
            "machine_code": meta.get("machine_code", "?"),
            "machine_type": meta.get("machine_type", "?"),
            "timeseries_label": meta.get("timeseries_label", ""),
            "description": meta.get("description") or getattr(e, "description", ""),
            "value_before": meta.get("value_before"),
            "value_after": meta.get("value_after"),
            "current_value": meta.get("current_value"),
            "baseline_avg": meta.get("baseline_avg"),
            "baseline_max": meta.get("baseline_max"),
            "shift": meta.get("shift"),
            "training_samples": meta.get("training_samples"),
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    if machine_type:
        df = df[df["machine_type"] == machine_type]
    if machine_code:
        df = df[df["machine_code"] == machine_code]
    if patterns:
        df = df[df["pattern"].isin(patterns)]

    df = df.sort_values("start_time", ascending=False).reset_index(drop=True)
    return df
