"""
Local-dev-friendly Cognite client factory for the streamlit/ app.

Why this exists
----------------
When this code runs INSIDE a CDF-hosted Streamlit app (Fusion > Build
Solutions > Streamlit apps), Cognite's runtime authenticates as the logged-in
Fusion user and `CogniteClient()` / `AsyncCogniteClient()` can be built with
*no arguments* -- see https://docs.cognite.com/cdf/streamlit

When you run the same code locally (`streamlit run streamlit/main.py` in a
normal terminal), there is no Fusion runtime behind it, so the zero-argument
call has nothing to authenticate with. This module tries the zero-arg form
first (so the exact same code works once deployed) and falls back to an
explicit OAuth client-credentials config built from a local .env file
otherwise.

Setup for local dev
--------------------
1. Copy .env.example (repo root) to .env and fill in a client ID/secret with
   access to your CDF project. This project (alimentospolarcomercialca) is a
   DataMosaix / Auth0-backed CDF project, not Azure AD -- auth goes through
   Auth0's token endpoint with a fixed `audience`, matching the pattern in
   notebooks/TestFTDataMosaix.ipynb. Ask whoever administers the project for
   a client ID/secret if you don't have one.
2. `.env` is already in .gitignore -- never commit real credentials.
3. `pip install python-dotenv` (already in streamlit/requirements.txt).

If Cognite changes how Fusion injects credentials, the zero-arg call may
start raising a different exception -- adjust the `except` clause below if
local fallback stops triggering correctly.
"""
from __future__ import annotations

import os

from cognite.client import AsyncCogniteClient, ClientConfig, CogniteClient
from cognite.client.credentials import OAuthClientCredentials

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _config_from_env() -> ClientConfig:
    missing = [
        var
        for var in ("BASE_URL", "PROJECT", "TOKEN_URL", "CDF_CLIENT_ID", "CDF_CLIENT_SECRET")
        if not os.getenv(var)
    ]
    if missing:
        raise RuntimeError(
            "Missing local-dev CDF credentials in your environment/.env: "
            f"{', '.join(missing)}. Copy .env.example to .env and fill it in, "
            "or run this app inside CDF Fusion where credentials are automatic."
        )

    base_url = os.environ["BASE_URL"]

    return ClientConfig(
        client_name="local-dev",
        project=os.environ["PROJECT"],
        base_url=base_url,
        credentials=OAuthClientCredentials(
            token_url=os.environ["TOKEN_URL"],
            client_id=os.environ["CDF_CLIENT_ID"],
            client_secret=os.environ["CDF_CLIENT_SECRET"],
            audience="https://cognitedata.com",
            scopes=[],
        ),
    )


def get_client() -> CogniteClient:
    """Sync client. Use in scripts, notebooks, or Cognite Functions tests."""
    try:
        return CogniteClient()
    except Exception:
        return CogniteClient(_config_from_env())


def get_async_client() -> AsyncCogniteClient:
    """Async client -- drop-in for cdf_service.py's get_cognite_client()."""
    try:
        return AsyncCogniteClient()
    except Exception:
        return AsyncCogniteClient(_config_from_env())
