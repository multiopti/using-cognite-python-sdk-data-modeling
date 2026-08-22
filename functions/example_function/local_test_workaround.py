"""
Same as local_test.py, but uses utils/cdf_rest_client.py instead of
cdf_auth.py: cognite-sdk 8.10.0 hangs on real API calls on this machine
(see cdf_rest_client.py's docstring), so this gets a working client via
direct REST calls instead. handler.py itself is untouched and stays
written against the real SDK's interface -- only the *local* auth/client
plumbing differs here.

Run:
    E:\\source\\repos\\streamlit\\myenv\\Scripts\\python functions\\example_function\\local_test_workaround.py
"""
import sys
from pathlib import Path

THIS_DIR = Path(__file__).parent
REPO_ROOT = THIS_DIR.parents[1]

sys.path.insert(0, str(THIS_DIR))
sys.path.insert(0, str(REPO_ROOT / "utils"))

from handler import handle  # noqa: E402
from cdf_rest_client import get_client  # noqa: E402

if __name__ == "__main__":
    client = get_client()
    result = handle(client=client, data={"asset_name_prefix": None})
    print(result)
