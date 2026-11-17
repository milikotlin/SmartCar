"""Draw a random sample of the Israeli vehicle registry (data.gov.il, same CKAN
resource the backend uses) so Sprint 3 can measure how well each training
dataset matches the vehicles the system will really see at runtime.

Usage: python -I ml/src/sample_gov_registry.py [n_chunks]   (1000 records per chunk)
"""
import json
import random
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import INTERIM_DIR  # noqa: E402

RESOURCE_ID = "053cea08-09bc-40ec-8f7a-156f0677aff3"
URL = "https://data.gov.il/api/3/action/datastore_search"


def fetch(offset: int, limit: int = 1000) -> dict:
    qs = urllib.parse.urlencode({"resource_id": RESOURCE_ID, "limit": limit, "offset": offset})
    req = urllib.request.Request(f"{URL}?{qs}", headers={"User-Agent": "smartcar-ml-research"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)["result"]


def main(n_chunks: int = 20) -> None:
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    total = fetch(0, 1)["total"]
    print(f"registry size: {total:,}")
    rng = random.Random(42)
    # Disjoint random chunks (a chunk = 1000 consecutive rows; registry order is not by make/year).
    offsets = rng.sample(range(0, total - 1000, 1000), n_chunks)
    frames = [pd.DataFrame(fetch(o)["records"]) for o in offsets]
    df = pd.concat(frames, ignore_index=True)
    out = INTERIM_DIR / "gov_registry_sample.csv"
    df.to_csv(out, index=False, encoding="utf-8")
    print(f"saved {len(df):,} rows -> {out}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20)
