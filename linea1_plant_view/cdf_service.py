import streamlit as st

from cdf_auth import get_async_client
from config import ELEMENTS


@st.cache_resource
def get_cognite_client():
    return get_async_client()


client = get_cognite_client()


async def load_line1_values() -> dict:
    """
    Latest value of each LINE1_*_SHIFT rollup timeseries referenced in
    config.ELEMENTS, keyed by external_id. hourly_production_report
    recomputes and re-inserts a fresh datapoint on these once per hour (see
    _write_line_type_rollups in functions/hourly_production_report/
    handler.py), so "latest" is effectively "this shift so far".

    A target missing entirely (e.g. renamed/deleted upstream) is dropped
    rather than raising, so one bad external_id doesn't blank the whole
    dashboard -- main.py falls back to "--" for that element.
    """
    ext_ids = [el["target"] for el in ELEMENTS]
    result = await client.time_series.data.retrieve_latest(external_id=ext_ids, ignore_unknown_ids=True)

    values = {}
    for item in result:
        dps = item.dump().get("datapoints") or []
        if dps:
            values[item.external_id] = dps[0]["value"]
    return values
