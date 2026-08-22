"""
Quick local sanity check for handle() before deploying it as a Cognite
Function. Uses the same local-dev auth helper as the Streamlit app, so it
needs the same .env (see env.example at the repo root).

Run:
    E:\\source\\repos\\streamlit\\myenv\\Scripts\\python functions\\example_function\\local_test.py
"""
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
    result = handle(client=client, data={"asset_name_prefix": None})
    print(result)
