"""
Same pattern as functions/hourly_production_report/local_test.py: run the
same handle() code locally against real CDF data, authenticated via
cdf_auth.py + .env (see env.example at the repo root).

By default this is a dry run against a single machine -- reads real data,
computes real detections, but writes nothing (dry_run=True). Drop
machine_codes to scan all machines, drop dry_run (or set False) to
actually write the detected anomaly events.

Run:
    E:\\source\\repos\\streamlit\\myenv\\Scripts\\python functions\\timeseries_anomaly_detector\\local_test.py
"""
import json
import sys
from pathlib import Path

THIS_DIR = Path(__file__).parent
REPO_ROOT = THIS_DIR.parents[1]

sys.path.insert(0, str(REPO_ROOT / "streamlit"))
sys.path.insert(0, str(THIS_DIR))

from handler import handle  # noqa: E402
from cdf_auth import get_client  # noqa: E402

if __name__ == "__main__":
    client = get_client()
    result = handle(client=client, data={"machine_codes": ["di11"], "dry_run": True})
    print(json.dumps(result, indent=2, ensure_ascii=False))
