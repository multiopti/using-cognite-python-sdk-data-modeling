"""
Local sanity check for handle() before deploying, same pattern as
../hourly_production_report/local_test.py: get_client() authenticates
against the REAL CDF project, and handle() reads REAL events / files from
it. dry_run=True (the default here) computes everything from live reads but
skips the final re-upload to CDF Files, so a first run can't surprise you.

Run:
    E:\\source\\repos\\streamlit\\myenv\\Scripts\\python functions\\shift_excel_report\\local_test.py
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
    result = handle(client=client, data={"dry_run": True})
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
