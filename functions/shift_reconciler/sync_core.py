"""
Copies hourly_production_report's handler.py/config.py into this folder as
hourly_core.py/config.py, so shift_reconciler's deploy zip and local tests
always run the exact same counter-delta/event-generation logic as the live
hourly function -- one canonical implementation in functions/
hourly_production_report/, two deployment targets. Cognite Functions can't
import code across separate deployed functions, so this copy step is the
packaging mechanism that avoids hand-maintaining two copies of that logic.

Run this before every local test and before rebuilding the deploy zip. Do
not hand-edit hourly_core.py or config.py in this folder -- edit the
originals in functions/hourly_production_report/ and re-run this script.
"""
import shutil
from pathlib import Path

THIS_DIR = Path(__file__).parent
SRC_DIR = THIS_DIR.parent / "hourly_production_report"

if __name__ == "__main__":
    shutil.copy(SRC_DIR / "handler.py", THIS_DIR / "hourly_core.py")
    shutil.copy(SRC_DIR / "config.py", THIS_DIR / "config.py")
    print(f"Synced hourly_core.py and config.py from {SRC_DIR}")
