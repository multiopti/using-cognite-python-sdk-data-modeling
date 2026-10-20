"""Plant-floor server: runs the Fusion Streamlit apps outside CDF and keeps them running.

    python planta_local\\planta_server.py

Starts one Streamlit process per app (through run_app.py) plus a small static server for the TV
rotation page, restarts any process that dies, and writes logs to planta_local\\logs\\. Meant to
be launched at boot by the scheduled task that install_service.ps1 creates.

    http://<server>:8500/tv.html   TV: rotates Línea 1 / Línea 3 (tv.html?s=30 sets the seconds)
    http://<server>:8501           Línea 1 - Vista de Planta
    http://<server>:8502           Línea 3 - Vista de Planta
    http://<server>:8503           Reporte de Producción (operators, read-only)
"""
import functools
import http.server
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LOGS = HERE / "logs"
LOGS.mkdir(exist_ok=True)

TV_PORT = 8500
REFRESH_S = 60            # every app re-reads CDF this often (viewers keep their filters)
APPS = [
    # (app folder, port, read_only)
    ("linea1_plant_view", 8501, True),
    ("linea3_plant_view", 8502, True),
    ("streamlit", 8503, True),            # Reporte de Producción
]


def log(msg):
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line, flush=True)
    with open(LOGS / "planta_server.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def start_app(folder, port, read_only):
    env = dict(os.environ, PLANT_REFRESH_S=str(REFRESH_S), PLANT_READ_ONLY="1" if read_only else "0",
               PYTHONUTF8="1")
    cmd = [sys.executable, "-m", "streamlit", "run", str(HERE / "run_app.py"),
           "--server.port", str(port), "--server.address", "0.0.0.0", "--server.headless", "true",
           "--client.toolbarMode", "viewer", "--browser.gatherUsageStats", "false",
           "--theme.base", "light",              # the apps were designed for Fusion's light theme
           "--", folder]
    out = open(LOGS / f"{folder}.log", "a", encoding="utf-8")
    log(f"starting {folder} on :{port}")
    return subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=out, stderr=subprocess.STDOUT)


def serve_tv():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(HERE / "tv"))
    handler.log_message = lambda *a, **k: None
    httpd = http.server.ThreadingHTTPServer(("0.0.0.0", TV_PORT), handler)
    log(f"TV page on :{TV_PORT}/tv.html")
    httpd.serve_forever()


def main():
    threading.Thread(target=serve_tv, daemon=True).start()
    procs = {app: start_app(*app) for app in APPS}
    restarts = {app: 0 for app in APPS}
    try:
        while True:
            time.sleep(10)
            for app, p in procs.items():
                if p.poll() is not None:
                    restarts[app] += 1
                    wait = min(300, 10 * restarts[app])          # back off if it keeps crashing
                    log(f"{app[0]} exited with code {p.returncode}; restarting in {wait}s")
                    time.sleep(wait)
                    procs[app] = start_app(*app)
    except KeyboardInterrupt:
        log("stopping")
        for p in procs.values():
            p.terminate()


if __name__ == "__main__":
    main()
