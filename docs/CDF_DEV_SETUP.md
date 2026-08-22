# Developing for Cognite Data Fusion (CDF) -- environment guide

This repo mixes two different kinds of CDF development that behave very
differently. Knowing which one you're in matters more than any specific
library version.

## 1. Two runtimes, not one

**Streamlit apps hosted inside CDF Fusion** (Build Solutions > Streamlit
apps) do NOT run on a normal Python server. They run on
[stlite](https://github.com/whitphx/stlite): Streamlit compiled to
WebAssembly via Pyodide, executing entirely in the visitor's browser. That
means:

- Single-threaded, browser-based event loop -- a blocking synchronous call
  freezes the UI until it returns. This is why `streamlit/cdf_service.py`
  uses `AsyncCogniteClient` and `async def` functions, and why `main.py` and
  `dashboard.py` use `await` at the top level of the script -- CDF's hosted
  runtime is built to expect this style for anything that talks to CDF.
- Only pure-Python packages install (via micropip). No compiled/native
  wheels unless Pyodide ships a prebuilt one -- pandas, numpy and plotly do;
  most other C-extension packages don't. `streamlit/requirements-cdf.txt` is
  what you paste into the app's "Manage packages" panel inside Fusion; it's
  a different list from the one you `pip install` locally.
- CDF authenticates the running user automatically -- no login code needed
  in the app itself while it's hosted there.
- No multithreading, and CORS restricts calls to non-CDF external services.

**Running the same code locally** (`streamlit run streamlit\main.py` in a
terminal, using your `myenv` venv) uses ordinary CPython Streamlit instead.
Plain CPython does not allow `await` at the top level of a script the way
Fusion's patched runtime does, so a straight `streamlit run` of the current
`main.py`/`dashboard.py` as-is may raise a `SyntaxError`. Two ways to test
locally without fighting that:

- **Fastest for logic/UI iteration:** temporarily wrap the script body in an
  `async def main(): ...` and call it with `asyncio.run(main())` at the
  bottom, guarded by `if __name__ == "__main__":`. Streamlit re-executes the
  whole file on every rerun, so a fresh `asyncio.run()` each time is fine.
- **Closest to the real thing:** install
  [stlite](https://github.com/whitphx/stlite) (or stlite-desktop) locally so
  you're testing on the actual Pyodide runtime, single-threaded behavior
  included, before you deploy. See the community write-up
  ["Simulating CDF Environment Locally for Streamlit App"](https://hub.cognite.com/streamlit-beta-285/simulating-cdf-environment-locally-for-streamlit-app-5010)
  for the current recommended approach -- worth reading in full before you
  invest time in either option.

**Cognite Functions** (`functions/`) are the opposite: plain server-side
CPython, no Pyodide, no browser sandbox. Any PyPI package with a compatible
wheel works. Use Functions for anything CPU-heavy, anything needing a
compiled dependency (e.g. `InDSL`), or scheduled/background jobs -- then
have the Streamlit app call the function or read what it wrote, rather than
doing the heavy work in-browser. This split is the pattern Cognite's own
staff recommend in
["Bullet-proofing Streamlit Apps in Cognite Data Fusion"](https://hub.cognite.com/cognite-data-fusion-toolkit-277/bullet-proofing-streamlit-apps-in-cognite-data-fusion-4534).

## 2. Auth: three different situations

| Where the code runs | How to authenticate |
|---|---|
| Streamlit app hosted in CDF Fusion | Automatic -- `CogniteClient()` / `AsyncCogniteClient()` with no arguments picks up the logged-in Fusion user. Nothing to configure. |
| Cognite Function | Automatic -- CDF injects an authenticated `client` argument into `handle()`. |
| Anything running on your own machine (`streamlit run`, `local_test.py`, notebooks) | Not automatic -- you need real credentials. |

For local dev, this repo now has `env.example` (repo root) and
`streamlit/cdf_auth.py`:

1. Copy `env.example` to `.env` and fill in `BASE_URL`, `PROJECT`,
   `TOKEN_URL`, `CDF_CLIENT_ID`, `CDF_CLIENT_SECRET` with a client ID/secret
   that has access to your project. This project (alimentospolarcomercialca)
   is DataMosaix / Auth0-backed, not Azure AD -- see
   `notebooks/TestFTDataMosaix.ipynb` for the reference pattern (fixed
   `audience="https://cognitedata.com"`, empty `scopes`). Ask your CDF admin
   for a client ID/secret if you don't have one (note `utils/cognite_auth.py`
   is unrelated leftover from the Cognite Academy course clone and points at
   Cognite's own training tenant/project via Azure AD, not this project).
2. `.env` is already covered by `.gitignore` -- it will never get committed.
3. `streamlit/cdf_auth.py` exposes `get_client()` / `get_async_client()`:
   they try the zero-argument Fusion-style call first, and fall back to the
   `.env`-based config when that fails (i.e. when running locally). This is
   a drop-in replacement for the `AsyncCogniteClient()` call currently at
   the top of `cdf_service.py` if you want `main.py`/`dashboard.py` to be
   runnable outside of Fusion too -- swap that one line for
   `from cdf_auth import get_async_client` /
   `client = get_async_client()`.

## 3. Local Python environment

You already have a venv at `myenv/`. Install the app's dependencies into it:

```
myenv\Scripts\pip install -r streamlit\requirements.txt
```

`myenv\` wasn't previously covered by `.gitignore` (only `.venv/`, `venv/`,
`env/`, `ENV/` were listed) -- it's been added now so the venv itself never
gets committed.

## 4. Cognite Functions (`functions/`)

`functions/example_function/` is a minimal starter:

- `handler.py` -- the `handle()` entry point. CDF inspects its signature and
  supplies whichever of `client`, `data`, `secrets`, `function_call_info`
  you declare.
- `requirements.txt` -- extra pip deps for this function only. Whatever's
  listed here is `pip install`ed fresh into the function's own environment
  at every deploy (per Cognite's docs), so `cognite-sdk` is pinned to an
  exact version (matching what's installed in `myenv` and tested via
  `local_test.py`) rather than left unpinned or omitted -- an open-ended
  `>=` constraint would let each deploy silently pick up a different SDK
  version than what was tested locally.
- `local_test.py` -- calls `handle()` locally with a real authenticated
  client (via `cdf_auth.get_client()`) so you can sanity-check logic before
  deploying. Note this only exercises the Auth0 client-credentials auth path
  from `.env` -- the real deployed Function gets a different, pre-instantiated
  `client` from CDF itself (on-behalf-of session flow), so this doesn't test
  auth end-to-end, only the handler logic against live data.

Deploy with the SDK directly:

```python
from cognite.client import CogniteClient
client = CogniteClient()  # or cdf_auth.get_client() locally
func = client.functions.create(
    name="example-function",
    external_id="example-function",
    folder="functions/example_function",
)
```

or manage it as code via the Cognite Toolkit (next section).

## 5. Cognite Toolkit (`cdf-tk`) -- deploying as code

The Toolkit is Cognite's CLI for managing CDF configuration (including
Streamlit apps and Functions) as version-controlled "modules" instead of
clicking through Fusion's UI.

```
pip install cognite-toolkit
cdf --help
```

The exact subcommands (module scaffolding, build, deploy, auth) have
changed between toolkit releases, so treat the following as a starting
point to confirm against `cdf --help` / `cdf modules --help` for the
version you install, and against the current
[resource library reference](https://docs.cognite.com/cdf/deploy/cdf_toolkit/references/resource_library)
for the exact `config.yaml` schema for Streamlit and Functions resources:

```
cdf auth verify         # confirm your CDF login/credentials work
cdf modules init        # interactive wizard, scaffolds a modules/ folder
cdf modules add         # add a Streamlit and/or Functions module template
cdf build               # renders the modules into a deployable build/ folder
cdf deploy --dry-run    # preview what would change in your CDF project
cdf deploy              # apply it
```

This hasn't been scaffolded into the repo yet since the exact module schema
is version-dependent -- worth doing as a deliberate next step once you've
confirmed the commands above against your installed toolkit version, so the
generated files match what your `cdf-tk` actually expects.

## 6. Suggested next steps, in order

1. `pip install -r streamlit\requirements.txt` into `myenv`.
2. Copy `env.example` to `.env`, fill in real (non-production-critical, or
   scoped-down) credentials, confirm `python functions\example_function\local_test.py`
   can reach your CDF project.
3. Decide whether to wire `cdf_auth.get_async_client()` into
   `cdf_service.py` so the app is runnable locally, or keep local testing to
   stlite only -- either is reasonable, it's a style choice.
4. Try `cdf --help` locally once, skim the resource library reference
   linked above, and only then scaffold a real `modules/` folder for
   deploying `streamlit/` and `functions/example_function/` as code.

## Sources

- [Streamlit apps - Cognite Docs](https://docs.cognite.com/cdf/streamlit)
- [Simulating CDF Environment Locally for Streamlit App](https://hub.cognite.com/streamlit-beta-285/simulating-cdf-environment-locally-for-streamlit-app-5010)
- [Bullet-proofing Streamlit Apps in Cognite Data Fusion](https://hub.cognite.com/cognite-data-fusion-toolkit-277/bullet-proofing-streamlit-apps-in-cognite-data-fusion-4534)
- [Limitations on package installation (InDSL) in CDF Streamlit apps](https://hub.cognite.com/streamlit-early-adopter-285/limitations-on-package-installation-indsl-library-when-making-streamlit-apps-in-cdf-3550)
- [About Cognite Functions](https://docs.cognite.com/cdf/functions)
- [Use Functions - Cognite Docs](https://docs.cognite.com/cdf/functions/use_functions)
- [cognite-sdk Functions reference](https://cognite-sdk-python.readthedocs-hosted.com/en/latest/functions.html)
- [Working with the Cognite Toolkit](https://docs.cognite.com/cdf/deploy/cdf_toolkit)
- [cognite-toolkit on GitHub](https://github.com/cognitedata/toolkit)
- [Cognite Toolkit resource library reference](https://docs.cognite.com/cdf/deploy/cdf_toolkit/references/resource_library)
