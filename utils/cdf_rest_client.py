"""
Minimal REST-based CogniteClient workaround for LOCAL DEV on this machine.

Why this exists
----------------
cognite-sdk 8.10.0's own HTTP client hangs indefinitely on this machine when
making an authenticated API call through the real CogniteClient (both the
sync and async client, reproduced identically via Git Bash and native
PowerShell) -- even though every individual piece it depends on works fine
in well under a second when called directly: a plain `requests` call to the
same endpoint, `httpx.AsyncClient` (including with the SDK's own exact
connection-pool `Limits` settings), and authlib's `OAuth2Client.fetch_token`
(the exact call the SDK uses internally for Auth0 token refresh). That
isolates it to a concurrency bug in the SDK's own request/retry
orchestration, not this project's code, auth, or network -- see the session
that diagnosed this for the full step-by-step isolation.

This module works around it by talking to the CDF REST API directly with
`requests` (for data calls) and `authlib` (for the Auth0 token, matching
cognite-sdk's own credential flow exactly). It exposes just enough of the
real CogniteClient's shape (currently: `.assets.list()`, `.config.project`)
for `handle()` functions written against the SDK to run unmodified locally.

This is LOCAL DEV ONLY. A deployed CDF Function runs inside CDF's own
hosted runtime with a real, working CogniteClient injected by CDF -- this
workaround is never involved there, so `handler.py` files should keep being
written against the real SDK's interface.

If a future cognite-sdk release fixes the underlying hang (8.13.0 was
already available and unverified at the time this was written), prefer
switching back to cdf_auth.get_client() and deleting this file.
"""
from __future__ import annotations

import os
import re
import time
from types import SimpleNamespace
from typing import Any

import requests
from authlib.integrations.httpx_client import OAuth2Client

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

_REQUIRED_ENV_VARS = ("BASE_URL", "PROJECT", "TOKEN_URL", "CDF_CLIENT_ID", "CDF_CLIENT_SECRET")
_AUDIENCE = "https://cognitedata.com"
_API_SUBVERSION = "20230101"
_TOKEN_EXPIRY_LEEWAY_SECONDS = 60


def _camel_to_snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _to_namespace(item: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(**{_camel_to_snake(k): v for k, v in item.items()})


class _TokenCache:
    """Mirrors cognite-sdk's OAuthClientCredentials token caching/refresh."""

    def __init__(self, token_url: str, client_id: str, client_secret: str) -> None:
        self._token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._access_token: str | None = None
        self._expires_at: float = 0.0

    def get(self) -> str:
        if self._access_token is None or time.time() > self._expires_at - _TOKEN_EXPIRY_LEEWAY_SECONDS:
            oauth = OAuth2Client(client_id=self._client_id, token_endpoint=self._token_url)
            creds = oauth.fetch_token(url=self._token_url, client_secret=self._client_secret, audience=_AUDIENCE)
            self._access_token = creds["access_token"]
            self._expires_at = time.time() + float(creds["expires_in"])
        return self._access_token


class RestAssetsAPI:
    def __init__(self, client: "RestCogniteClient") -> None:
        self._client = client

    def list(self, name: str | None = None, limit: int = 100) -> list[SimpleNamespace]:
        """Matches cognite-sdk AssetsAPI.list()'s wire format: POST /assets/list.

        Note: like the real SDK, `name` is an exact match, not a prefix filter.
        """
        body: dict[str, Any] = {"limit": limit}
        if name:
            body["filter"] = {"name": name}
        resp = self._client._post("/assets/list", json=body)
        return [_to_namespace(item) for item in resp.json().get("items", [])]


class RestConfig:
    def __init__(self, project: str) -> None:
        self.project = project


class RestCogniteClient:
    """Drop-in-enough substitute for CogniteClient's shape, for local dev only."""

    def __init__(self) -> None:
        missing = [v for v in _REQUIRED_ENV_VARS if not os.getenv(v)]
        if missing:
            raise RuntimeError(
                f"Missing local-dev CDF credentials in your environment/.env: {', '.join(missing)}. "
                "Copy env.example to .env (repo root) and fill it in."
            )

        self._base_url = os.environ["BASE_URL"]
        self.config = RestConfig(project=os.environ["PROJECT"])
        self._token_cache = _TokenCache(
            token_url=os.environ["TOKEN_URL"],
            client_id=os.environ["CDF_CLIENT_ID"],
            client_secret=os.environ["CDF_CLIENT_SECRET"],
        )
        self.assets = RestAssetsAPI(self)

    def _post(self, resource_path: str, json: dict[str, Any]) -> requests.Response:
        url = f"{self._base_url}/api/v1/projects/{self.config.project}{resource_path}"
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {self._token_cache.get()}",
                "cdf-version": _API_SUBVERSION,
                "content-type": "application/json",
            },
            json=json,
            timeout=30,
        )
        resp.raise_for_status()
        return resp


def get_client() -> RestCogniteClient:
    """Local-dev-only substitute for cdf_auth.get_client()."""
    return RestCogniteClient()
