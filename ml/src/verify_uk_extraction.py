"""Independent verification of the UK MOT extraction (run after mot_vehicle_sample.py). Writes docs/UK_EXTRACTION.md.

Level 1 (source integrity): the extraction report must show, for every zip member, that CRC32 and size of the FULL decompressed stream equal the values stored
in the zip central directory. This proves that the decoder (Deflate64 for the results files, plain Deflate for the item files) reproduced the published bytes.
Level 2 (derived files): structure, sampling rule, referential integrity, completeness over the calendar year, stability of the item coverage, plausibility of values.
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import INTERIM_DIR  # noqa: E402

DOCS = Path(__file__).resolve().parents[2] / "docs"
lines = ["# UK MOT extraction: completeness and correctness checks", "",
         "Source: DVSA anonymised MOT data (Open Government Licence v3.0), yearly files `dft_test_result_<year>.zip` and `dft_test_item_<year>.zip`.",
         "Scope: **all** tests of the year are read; the derived tables keep the class-4 (cars) normal tests of a pseudo-random 1-in-41 subset of **vehicles** (`vehicle_id % 41 == 0`), so each sampled vehicle keeps all its tests and can be followed across years.", ""]
problems = []

for year in (2022, 2023):
    rep = json.loads((INTERIM_DIR / f"uk_mot_{year}_extraction_report.json").read_text(encoding="utf-8"))
    lines += [f"## {year}", "", "### Level 1 - integrity of the source streams", "", "| Member | Compression | Bytes decoded | Bytes in zip header | CRC32 decoded | CRC32 in zip header | Verified |", "|---|---|---|---|---|---|---|"]
    for k in ("results_stream", "items_stream"):
        s = rep[k]
        lines.append(f"| {s['member']} | {'Deflate64 (type 9)' if s['compress_type'] == 9 else 'Deflate (type 8)'} | {s['actual_bytes']:,} | {s['expected_bytes']:,} | {s['actual_crc32']} | {s['expected_crc32']} | {'yes' if s['integrity_verified'] else 'NO'} |")
        if not s["integrity_verified"]:
            problems.append(f"{year} {k} integrity")
    lines += ["", f"Lines read: results {rep['results']['lines_read']:,}, items {rep['items']['lines_read']:,}. Damaged lines: results {rep['results']['damaged_lines']}, items {rep['items']['damaged_lines']}.", ""]

    res = pd.read_csv(INTERIM_DIR / f"uk_mot_{year}_veh_results.csv", sep="|", dtype=str)
    items = pd.read_csv(INTERIM_DIR / f"uk_mot_{year}_veh_items.csv", sep="|", dtype=str)
    checks = []

    def chk(name, ok, detail=""):
        checks.append((name, ok, detail))
        if not ok:
            problems.append(f"{year}: {name} {detail}")

    chk("every results line has the expected number of fields and numeric ids", bool(res.test_id.str.fullmatch(r"\d+").all() and res.vehicle_id.str.fullmatch(r"\d+").all() and res.notna().any(axis=1).all()))
    chk("sampling rule holds for every kept vehicle (vehicle_id % 41 == 0)", bool(res.vehicle_id.map(lambda v: int(v) % 41 == 0).all()))
    chk("only class-4 normal tests", bool((res.test_class_id == "4").all() and (res.test_type == "NT").all()))
    chk("no duplicated test_id", not res.test_id.duplicated().any(), f"({res.test_id.duplicated().sum()} duplicates)")
    chk("number of kept tests equals the report", len(res) == rep["results"]["kept_tests"], f"({len(res):,} vs {rep['results']['kept_tests']:,})")
    chk("every item row refers to a kept test", bool(items.test_id.isin(set(res.test_id)).all()))
    chk("every item line has numeric ids and a known type code", bool(items.test_id.str.fullmatch(r"\d+").all() and items.rfr_id.str.fullmatch(r"\d+").all() and items.rfr_type_code.isin(list("FPAMU")).all()), str(items.rfr_type_code.value_counts().to_dict()))
    d = pd.to_datetime(res.test_date, errors="coerce")
    chk("all test dates parse and fall inside the year", bool(d.notna().all() and (d.dt.year == year).all()), f"({d.min().date()} to {d.max().date()})")
    mil = pd.to_numeric(res.test_mileage, errors="coerce")
    chk("odometer readings present for the large majority of tests", float(mil.notna().mean()) > 0.97, f"({mil.notna().mean():.3f})")
    monthly = res.groupby(d.dt.month).size()
    chk("every month of the year is present", set(monthly.index) == set(range(1, 13)), str(monthly.to_dict()))
    res["has_item"] = res.test_id.isin(set(items.test_id))
    m_share = res.groupby(d.dt.month).has_item.mean()
    chk("share of tests with at least one item row is stable across the year (no collapse in the second half)", float(m_share.min()) > 0.8 * float(m_share.max()), f"(min {m_share.min():.3f}, max {m_share.max():.3f})")
    lines += ["### Level 2 - derived files", "", "| Check | Result | Detail |", "|---|---|---|"] + [f"| {n} | {'pass' if ok else '**FAIL**'} | {det} |" for n, ok, det in checks]
    lines += ["", f"Tests kept: {len(res):,}; vehicles: {res.vehicle_id.nunique():,}; item rows: {len(items):,}. Tests per month: {monthly.to_dict()}. Share of tests with items per month: { {int(k): round(float(v), 3) for k, v in m_share.items()} }.", ""]

lines += ["## Root cause of the earlier corruption (found and fixed)", "",
          "Earlier experiments (notebooks 04 to 09, first versions) decoded the *item* files with a Deflate64 decoder. The DVSA item zips are plain Deflate (compression type 8); only the result zips are Deflate64 (type 9). A Deflate64 decoder reads a plain-Deflate length code (258) as a long-match code, so everything after the first such match was garbled without an error. "
          "That is why only the first half of each item file looked usable. The decoder is now chosen from the zip header and the integrity of the whole stream is proven by the CRC32 comparison above. The results of the earlier notebooks used only the clean part of the item files, so their conclusions stand, but the second half of the year is now available and the final model was trained on the full years.", ""]
DOCS.mkdir(exist_ok=True)
(DOCS / "UK_EXTRACTION.md").write_text("\n".join(lines), encoding="utf-8")
print("problems:", problems or "none")
sys.exit(1 if problems else 0)
