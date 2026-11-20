"""
Local run of production_reports_to_s3 against the REAL CDF project (reads events), with the .env auth helper of
../../streamlit/cdf_auth.py and this PC's AWS CLI credentials for S3.

    python functions/production_reports_to_s3/local_test.py                      # dry run: last 3 hours
    python functions/production_reports_to_s3/local_test.py 2026-11-18           # dry run: that day's 2 shifts
    python functions/production_reports_to_s3/local_test.py 2026-11-18 standum32 --write   # REAL upload, one machine
    python functions/production_reports_to_s3/local_test.py 2026-08-01 2026-11-19 --write  # REAL backfill
"""
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
THIS_DIR = Path(__file__).parent
sys.path.insert(0, str(THIS_DIR.parents[1] / "streamlit"))
sys.path.insert(0, str(THIS_DIR))

from handler import handle  # noqa: E402
from cdf_auth import get_client  # noqa: E402

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--write"]
    dates = [a for a in args if a[:2] == "20" and len(a) == 10]
    machines = [a for a in args if a not in dates]
    data = {"dry_run": "--write" not in sys.argv}
    if dates:
        data["from"], data["to"] = dates[0], dates[-1]
    if machines:
        data["machines"] = machines
    print("data:", data)
    res = handle(get_client(), data)
    print(json.dumps(res, indent=1, ensure_ascii=False))
