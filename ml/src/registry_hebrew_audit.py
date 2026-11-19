"""READ-ONLY: which fields of the Israeli registry still reach the dashboard in Hebrew, and how many distinct values would need translating.

Run: ml/.venv/Scripts/python.exe -I -X utf8 ml/src/registry_hebrew_audit.py   (writes ml/registry_hebrew_audit.json)
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "backend"))
from config import INTERIM_DIR  # noqa: E402
import types  # noqa: E402

try:
    import pydantic  # noqa: F401
except ModuleNotFoundError:        # the research venv has no pydantic: a plain stand-in for the response schema is enough for this read-only audit
    stub = types.ModuleType("app.schemas.vehicle")
    stub.VehicleProfile = lambda **kw: types.SimpleNamespace(**kw)
    sys.modules["app.schemas.vehicle"] = stub
    sys.modules["app.schemas"] = types.ModuleType("app.schemas")
from app.services.translation import translate_vehicle_record  # noqa: E402

HEB = re.compile(r"[֐-׿]")
raw = pd.read_csv(INTERIM_DIR / "gov_registry_sample.csv")
raw = raw[raw.sug_degem == "P"]
rows = raw.to_dict("records")
prof = [translate_vehicle_record({k: (None if pd.isna(v) else v) for k, v in r.items()}) for r in rows]
out = {"vehicles": len(prof), "fields": {}}
for field in ("make", "model", "fuel_type", "ownership", "color", "trim_level"):
    vals = pd.Series([getattr(p, field) for p in prof], dtype="object")
    mask = vals.map(lambda v: bool(isinstance(v, str) and HEB.search(v)))
    top = vals[mask].value_counts().head(25)
    out["fields"][field] = {"share_with_hebrew": round(float(mask.mean()), 4), "distinct_hebrew_values": int(vals[mask].nunique()), "top_hebrew_values": {k: int(v) for k, v in top.items()}}
print(json.dumps(out, indent=1, ensure_ascii=False))
(ROOT / "ml" / "registry_hebrew_audit.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
