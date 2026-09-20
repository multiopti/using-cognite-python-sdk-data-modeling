"""
Local-dev-friendly Cognite client factory for the linea1_plant_view/ app.

Same pattern as the other apps in this repo (overview_dashboard/cdf_auth.py,
streamlit/cdf_auth.py, anomaly_monitor/cdf_auth.py): try the zero-argument
Fusion-style client first (works once deployed to CDF Fusion, where the
runtime authenticates as the logged-in user), and fall back to an explicit
OAuth client-credentials config from a local .env file for local dev/testing.

Setup for local dev
--------------------
1. Copy .env.example (repo root) to .env and fill in a client ID/secret with
   access to your CDF project. This project (alimentospolarcomercialca) is a
   DataMosaix / Auth0-backed CDF project, not Azure AD.
2. `.env` is already in .gitignore -- never commit real credentials.
3. `pip install python-dotenv` (already in linea1_plant_view/requirements.txt).
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
