"""
Local sanity check for handle() before deploying, using the same local-dev
auth helper as the Streamlit app (see ../../streamlit/cdf_auth.py and
../../env.example at the repo root).

By default this only runs ONE machine (di11) against the most recently
completed hour, so a test run doesn't write 25 events. Remove
"machine_codes" from the data dict below to run everything, or add
"hours_ago" to backfill a specific past hour.

Run:
    E:\\source\\repos\\streamlit\\myenv\\Scripts\\python functions\\hourly_production_report\\local_test.py
"""
import json
import sys
from pathlib import Path

THIS_DIR = Path(__file__).parent
REPO_ROOT = THIS_DIR.parents[1]

sys.path.insert(0, str(THIS_DIR))
sys.path.insert(0, str(REPO_ROOT / "streamlit"))

from handler import handle  # noqa: E402
from cdf_auth import get_client  # noqa: E402

if __name__ == "__main__":
    client = get_client()
    result = handle(client=client, data={"machine_codes": ["di11"]})
    print("\n--- RESULT ---")
    print(json.dumps(result, indent=2, ensure_ascii=False))
