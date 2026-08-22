"""
Local sanity check for handle() before deploying, using the same local-dev
auth helper as the Streamlit app (see ../../streamlit/cdf_auth.py and
../../env.example at the repo root).

"Local" only means the Python interpreter runs on your machine -- there is
no local copy of anything to test against. get_client() authenticates
against your REAL CDF project, and handler.py reads REAL time series /
asset data from it, exactly as it would running as a deployed Function.

Two safety nets are on by default so a first test run can't surprise you:
  - machine_codes limits the run to ONE machine (di11) instead of all ~25.
  - dry_run=True skips the final client.events.upsert() call entirely --
    everything is computed from live reads, but nothing is written. The
    printed/returned event payload shows exactly what WOULD be written.

Once you're happy with the output, flip dry_run to False (or remove it) to
actually write that one event, then remove machine_codes to run everything.

Run:
    E:\\source\\repos\\streamlit\\myenv\\Scripts\\python functions\\hourly_production_report\\local_test.py
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
    print("\n--- RESULT ---")
    print(json.dumps(result, indent=2, ensure_ascii=False))
