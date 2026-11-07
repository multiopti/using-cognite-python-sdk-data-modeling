"""
Backs up a CDF RAW table to gzipped JSON Lines, one row per line:
{"key", "last_updated_time", "columns"}. Written to
data_exports/raw_backup/ (git-ignored). Retries the whole download up to 3
times; CDF throttles large reads, so expect pauses of up to ~1 min.

Run (defaults to the plant's MQTT table):
    E:\\source\\repos\\streamlit\\myenv\\Scripts\\python utils\\backup_raw.py [db] [table]
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

DB = sys.argv[1] if len(sys.argv) > 1 else "db_superenvases_raw"
TABLE = sys.argv[2] if len(sys.argv) > 2 else "raw_mqtt_messages"
out_dir = REPO / "data_exports" / "raw_backup"
out_dir.mkdir(parents=True, exist_ok=True)
out = out_dir / f"{DB}.{TABLE}_{datetime.now():%Y%m%d_%H%M}.jsonl.gz"

c = get_client()


def dump():
    t0 = time.time()
    n = 0
    min_ts = max_ts = None
    with gzip.open(out, "wt", encoding="utf-8") as f:
        for chunk in c.raw.rows(DB, TABLE, chunk_size=10000, partitions=4):
            for r in chunk:
                f.write(json.dumps({"key": r.key, "last_updated_time": r.last_updated_time, "columns": r.columns}, ensure_ascii=False, default=str) + "\n")
                n += 1
                lut = r.last_updated_time
                min_ts = lut if min_ts is None or lut < min_ts else min_ts
                max_ts = lut if max_ts is None or lut > max_ts else max_ts
            print(f"{n:,} rows ({time.time() - t0:.0f}s)", flush=True)
    return t0, n, min_ts, max_ts


for attempt in range(1, 4):
    try:
        t0, n, min_ts, max_ts = dump()
        break
    except Exception as e:
        print(f"ATTEMPT {attempt} FAILED: {type(e).__name__}: {e}", flush=True)
        if attempt == 3:
            raise
        time.sleep(15)

fmt = lambda ms: datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M")  # noqa: E731
print(f"DONE: {n:,} rows -> {out} ({out.stat().st_size / 1e6:.1f} MB) in {time.time() - t0:.0f}s")
print(f"last_updated_time range: {fmt(min_ts)} .. {fmt(max_ts)}")
