"""
Deletes RAW rows of raw_mqtt_messages written before a cutoff -- but only
keys that are in a verified backup (see backup_raw.py), so nothing is ever
deleted without a copy. Resumable: it first lists the old keys still in CDF
and deletes only those, so a stopped run can simply be started again.

Delete rows, never the table itself: whoever writes into it (the plant's
MQTT extractor) isn't visible to this SDK account, and may not recreate it.

`expected` is the count you confirmed beforehand from the backup; the run
aborts if the backup gives a different number for the same cutoff.

Run:
    E:\\source\\repos\\streamlit\\myenv\\Scripts\\python utils\\delete_old_raw.py <backup.jsonl.gz> <cutoff, e.g. 2026-10-22T08:49-04:00> <expected>
"""
import gzip
import json
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "streamlit"))
from cdf_auth import get_client  # noqa: E402

DB, TABLE = "db_superenvases_raw", "raw_mqtt_messages"
BACKUP, CUTOFF, EXPECTED = sys.argv[1], datetime.fromisoformat(sys.argv[2]), int(sys.argv[3])

cutoff_ms = CUTOFF.timestamp() * 1000
keys = [r["key"] for r in map(json.loads, gzip.open(BACKUP, "rt", encoding="utf-8")) if r["last_updated_time"] < cutoff_ms]
print(f"keys to delete: {len(keys):,}", flush=True)
if abs(len(keys) - EXPECTED) > 50:
    sys.exit(f"ABORT: expected ~{EXPECTED:,} keys, got {len(keys):,}")

c = get_client()
backed_up = set(keys)
remaining = {r.key for r in c.raw.rows.list(DB, TABLE, limit=None, columns=[], max_last_updated_time=int(cutoff_ms))}
keys = [k for k in keys if k in remaining]
print(f"still in CDF before cutoff: {len(remaining):,} | to delete (in backup): {len(keys):,} | not in backup, kept: {len(remaining - backed_up):,}", flush=True)
t0 = time.time()
BATCH = 10000
for i in range(0, len(keys), BATCH):
    batch = keys[i:i + BATCH]
    for attempt in range(1, 6):
        try:
            c.raw.rows.delete(DB, TABLE, key=batch)
            break
        except Exception as e:
            print(f"  batch {i} attempt {attempt} failed: {type(e).__name__}: {e}", flush=True)
            if attempt == 5:
                raise
            time.sleep(10 * attempt)
    print(f"deleted {min(i + BATCH, len(keys)):,}/{len(keys):,} ({time.time() - t0:.0f}s)", flush=True)
print("DONE", flush=True)
