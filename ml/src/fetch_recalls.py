"""Download the Ministry of Transport dataset of vehicles with OPEN (not yet performed) recalls.

Source: https://data.gov.il/he/datasets/ministry_of_transport/hagbalat_recall
Fields: MISPAR_RECHEV (plate), RECALL_ID, SUG_RECALL, SUG_TAKALA (defect category), TEUR_TAKALA, TAARICH_PTICHA.
This is a real, per-plate, per-component FACT (not a probability) and is keyed by the same plate as the registry.
"""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import INTERIM_DIR  # noqa: E402

RESOURCE_ID = "36bf1404-0be4-49d2-82dc-2f1ead4a8b93"
URL = "https://data.gov.il/api/3/action/datastore_search"


def fetch(offset: int, limit: int) -> dict:
    qs = urllib.parse.urlencode({"resource_id": RESOURCE_ID, "limit": limit, "offset": offset})
    req = urllib.request.Request(f"{URL}?{qs}", headers={"User-Agent": "smartcar-ml-research"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)["result"]


def main() -> None:
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    limit, offset, frames, total = 20000, 0, [], None
    while total is None or offset < total:
        r = fetch(offset, limit)
        total = r["total"]
        frames.append(pd.DataFrame(r["records"]))
        offset += limit
    df = pd.concat(frames, ignore_index=True)
    out = INTERIM_DIR / "israel_open_recalls.csv"
    df.to_csv(out, index=False, encoding="utf-8")
    print(f"saved {len(df):,} open-recall records ({df['MISPAR_RECHEV'].nunique():,} distinct plates) -> {out}")


if __name__ == "__main__":
    main()
