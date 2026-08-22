"""
Example Cognite Function handler.

A Cognite Function is a plain server-side Python process (full CPython,
not the browser/Pyodide sandbox that CDF's Streamlit apps run under) -- so
any package on PyPI with a matching wheel for the function's Python runtime
works here, unlike streamlit/requirements-cdf.txt.

The entry point must be a function named `handle`. Only declare the
parameters you actually use -- CDF inspects the signature and supplies
whichever of these you ask for:

    client              : CogniteClient, pre-authenticated with the
                           permissions of whoever/whatever called the function
    data                : dict, the payload passed at call time
    secrets             : dict, values you registered as secrets when you
                           created the function (never pass secrets via data)
    function_call_info  : dict, metadata such as function_id, call_id,
                           schedule_id, scheduled_time

Deploy with the Python SDK, e.g.:

    from cognite.client import CogniteClient
    client = CogniteClient()
    func = client.functions.create(
        name="example-function",
        external_id="example-function",
        folder="functions/example_function",   # this folder
    )

...or as a Functions module via the Cognite Toolkit (cdf-tk) -- see
docs/CDF_DEV_SETUP.md and https://docs.cognite.com/cdf/functions for the
current module/config.yaml schema (check it against your installed toolkit
version with `cdf --help`, the schema does evolve).
"""
from __future__ import annotations


def handle(
    client: "CogniteClient" = None,  # noqa: F821 - injected by CDF at runtime
    data: dict | None = None,
) -> dict:
    data = data or {}
    name_prefix = data.get("asset_name_prefix")

    assets = client.assets.list(name=name_prefix, limit=10)

    return {
        "status": "ok",
        "count": len(assets),
        "external_ids": [a.external_id for a in assets],
    }
