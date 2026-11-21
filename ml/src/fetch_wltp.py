"""Download the official model table of the Ministry of Transport (data.gov.il, "תוצרים ודגמים של כלי רכב WLTP", resource 142afde2-...).

It gives, per manufacturer code + model code + year, the engine volume (nefah_manoa, cc) and whether the car is automatic (automatic_ind): the two Model 1
features of Smart_Car_Models.pdf that the vehicle registry itself does not carry. Used offline to build the Israeli registry sample for the CBS calibration;
the API looks the same table up per vehicle (app/services/vehicle_specs.py).

Run: ml/.venv/Scripts/python.exe -I -X utf8 ml/src/fetch_wltp.py   (writes INTERIM_DIR/wltp_models.csv)
"""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import INTERIM_DIR  # noqa: E402

RESOURCE = "142afde2-6228-49f9-8a29-9b6c3a0cbe40"
FIELDS = ["tozeret_cd", "degem_cd", "shnat_yitzur", "nefah_manoa", "automatic_ind", "delek_nm", "kinuy_mishari"]


def main() -> None:
    rows, offset = [], 0
    while True:
        q = urllib.parse.urlencode({"resource_id": RESOURCE, "limit": 32000, "offset": offset})
        req = urllib.request.Request(f"https://data.gov.il/api/3/action/datastore_search?{q}", headers={"User-Agent": "SmartCar-Ops academic project"})
        res = json.loads(urllib.request.urlopen(req, timeout=120).read().decode("utf-8"))["result"]
        rows += res["records"]
        offset += len(res["records"])
        print(f"{offset:,} / {res['total']:,}", flush=True)
        if not res["records"] or offset >= res["total"]:
            break
    df = pd.DataFrame(rows)[FIELDS]
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(INTERIM_DIR / "wltp_models.csv", index=False)
    print(f"written {INTERIM_DIR / 'wltp_models.csv'}: {len(df):,} rows")


if __name__ == "__main__":
    main()
