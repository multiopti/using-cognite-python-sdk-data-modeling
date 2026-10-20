"""Runs one of the CDF Fusion Streamlit apps unmodified on a regular (non-Fusion) Streamlit server.

    streamlit run planta_local/run_app.py -- linea1_plant_view

Fusion hosts the apps on stlite (Pyodide), which allows top-level `await` in main.py. Regular
Streamlit doesn't, so this wrapper compiles the app's main.py with top-level await allowed and
runs the resulting coroutine on one long-lived event loop per server process. The loop is shared
because each app caches its async CDF client (st.cache_resource), and that client's HTTP
connections belong to the loop that created them. A lock serializes the reruns of concurrent
viewers (a TV plus a few operator PCs), since one loop can't run two coroutines at once from
different threads.

Environment (set by planta_server.py):
    PLANT_REFRESH_S   re-run the app every N seconds (keeps each viewer's filters); 0 = off
    PLANT_READ_ONLY   "1" -> apps that allow editing (Reporte de Producción) show read-only
"""
import ast
import asyncio
import os
import sys
import threading
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent           # cognite-sdk/
APP_DIR = ROOT / sys.argv[1]
MAIN = APP_DIR / "main.py"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
os.chdir(ROOT)                                           # cdf_auth's load_dotenv() finds cognite-sdk/.env


@st.cache_resource
def _runtime():
    return asyncio.new_event_loop(), threading.Lock()


loop, lock = _runtime()
code = compile(MAIN.read_text(encoding="utf-8"), str(MAIN), "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
namespace = {"__name__": "__main__", "__file__": str(MAIN)}
with lock:
    result = eval(code, namespace)
    if asyncio.iscoroutine(result):
        loop.run_until_complete(result)

# Opened by the TV page (tv.html loads the apps with ?embed=true): hide Streamlit's own scrollbars,
# which otherwise show as a thin line on screen. Operator PCs (no embed) keep them.
if st.query_params.get("embed") == "true":
    st.markdown("<style>*::-webkit-scrollbar{display:none} *{scrollbar-width:none}</style>",
                unsafe_allow_html=True)

refresh_s = int(os.environ.get("PLANT_REFRESH_S", "0") or 0)
if refresh_s > 0:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=refresh_s * 1000, key="plant_autorefresh")
