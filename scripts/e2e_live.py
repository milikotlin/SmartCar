"""End-to-end test with REAL Israeli plates against the running stack (live data.gov.il, PostgreSQL, Redis, models).

For ~90 plates (random sample of the public registry, stratified by fuel and age; none of them used for training or seeding) it checks:
profile -> prediction -> invariants of every section; plus negative cases, cache timing and the chat endpoint. Writes docs/E2E_REPORT.md.

Usage:  python scripts/e2e_live.py [http://localhost:8000]
"""
import json
import statistics
import sys
import time
from datetime import date
from pathlib import Path

import httpx

API = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
HERE = Path(__file__).parent
PLATES = json.loads((HERE / "e2e_plates.json").read_text(encoding="utf-8"))
failures: list[str] = []
checks = 0


def check(cond: bool, msg: str) -> None:
    global checks
    checks += 1
    if not cond:
        failures.append(msg)


def main() -> None:
    rows, timings_cold, timings_warm, retries = [], [], [], []
    with httpx.Client(timeout=90) as c:
        check(c.get(f"{API}/health").json() == {"status": "ok"}, "health")
        for v in PLATES:
            plate = v["plate"]
            t0 = time.perf_counter()
            for attempt in range(4):                     # the public data.gov.il service is sometimes slow: the API answers 503, the test retries
                r = c.get(f"{API}/api/v1/predict/{plate}")
                if r.status_code != 503:
                    break
                retries.append(plate)
                time.sleep(4)
            timings_cold.append(time.perf_counter() - t0)
            if r.status_code != 200:
                check(False, f"{plate}: HTTP {r.status_code}")
                rows.append({**v, "status": r.status_code})
                continue
            t0 = time.perf_counter()
            r2 = c.get(f"{API}/api/v1/predict/{plate}")
            timings_warm.append(time.perf_counter() - t0)
            b = r.json()
            check(r2.json()["vehicle"] == b["vehicle"], f"{plate}: cached profile differs")
            veh, m, risk, mt, rc = b["vehicle"], b["mileage"], b["inspection_risk"], b["maintenance"], b["recalls"]
            check(veh["license_plate"] == plate, f"{plate}: plate mismatch")
            check(not any("֐" <= ch <= "׿" for ch in veh["make"]) or veh["make"] == veh["make_raw"], f"{plate}: make not translated ({veh['make_raw']!r})")
            check(m["estimated_low_km"] <= m["estimated_km"] <= m["estimated_high_km"], f"{plate}: mileage range does not bracket the estimate")
            check(m["primary_source"] == "estimated" and "not a measurement" in m["label"], f"{plate}: estimate not labelled as an estimate")
            age = date.today().year - veh["manufacture_year"]
            if age >= 1:
                check(m["estimated_km"] > 0, f"{plate}: zero mileage for age {age}")
            check(m["estimated_annual_km"] < 80_000, f"{plate}: implausible annual km {m['estimated_annual_km']}")
            fuel_ok = veh["fuel_type"] in ("Petrol", "Diesel", "Hybrid")
            if risk["covered"]:
                check(fuel_ok, f"{plate}: covered although fuel {veh['fuel_type']}")
                check(len(risk["systems"]) == 3 and risk["variant"] in ("cold", "cold_odo", "hist", "hist_odo"), f"{plate}: bad risk block")
                for s in risk["systems"]:
                    check(0 < s["foreign_probability"] < 1 and 1 <= s["percentile_same_age"] <= 99 and s["band"] in ("lower", "typical", "higher"), f"{plate}: bad system risk {s}")
            else:
                check(bool(risk["reasons"]) and risk["systems"] == [], f"{plate}: not covered without a reason")
            check(rc["kind"] == "official_recall" and (rc["available"] is False or rc["count"] == len(rc["items"])), f"{plate}: recall block inconsistent")
            keys = {x["key"] for x in mt["rules"]}
            check({"brakes", "brake_fluid", "tires", "filters"} <= keys and ("oil" not in keys or veh["fuel_type"] != "Electric"), f"{plate}: maintenance rules incomplete {sorted(keys)}")
            check(all(x["status"] in ("ok", "due_soon", "overdue", "no_record", "no_record_overdue") for x in mt["rules"]), f"{plate}: maintenance statuses")
            check(not any(x["status"] == "no_record_overdue" for x in mt["rules"]), f"{plate}: an estimated odometer must never prove an overdue service")
            rows.append({**v, "status": 200, "make_en": veh["make"], "est_km": m["estimated_km"], "range": (m["estimated_low_km"], m["estimated_high_km"]), "covered": risk["covered"],
                         "variant": risk["variant"], "bands": {s["system"]: s["band"] for s in risk["systems"]}, "recalls": rc["count"] if rc["available"] else None})

        # negative cases
        for bad in ("123456", "123456789", "abcdefgh", "1234567x"):
            check(c.get(f"{API}/api/v1/predict/{bad}").status_code == 422, f"invalid plate {bad} not rejected")
        check(c.get(f"{API}/api/v1/predict/10000001").status_code == 404, "non-existent plate not 404")

        # chat on a real plate (deterministic fallback unless OPENAI_API_KEY is configured)
        ok_plate = next(r["plate"] for r in rows if r.get("status") == 200)
        ch = c.post(f"{API}/api/v1/chat", json={"license_plate": ok_plate, "message": "Hearing a squeaking noise when braking"})
        check(ch.status_code == 200 and ch.json()["answer"] and ch.json()["context"], "chat answer")
        chat_source = ch.json().get("source")

    ok = [r for r in rows if r.get("status") == 200]
    covered = [r for r in ok if r["covered"]]
    lines = ["# End-to-end test with real Israeli plates", "",
             f"Run: {date.today().isoformat()} against `{API}` (live data.gov.il registry and recall services, PostgreSQL, Redis, exported models).", "",
             f"* plates tested: **{len(rows)}** (registry lookups answered: {len(ok)}); automatic checks: **{checks}**; failures: **{len(failures)}**",
             f"* Model 2 produced an estimate for {len(covered)} plates and declined {len(ok) - len(covered)} (electric, gas, or age outside 3-20 years, each with its reason)",
             f"* plates with at least one open recall: {sum(1 for r in ok if r['recalls'])}",
             f"* latency of `/api/v1/predict` (full request incl. live registry call): median {statistics.median(timings_cold):.2f} s cold, {statistics.median(timings_warm) * 1000:.0f} ms with the 24 h cache",
             f"* registry outages absorbed by the API's own retry and answered as 503, then retried by the test: {len(retries)}",
             f"* chat endpoint answered from: `{chat_source}`", ""]
    if failures:
        lines += ["## Failures", ""] + [f"* {f}" for f in failures] + [""]
    lines += ["## Sample of results", "", "| plate | make | year | fuel | estimated km (80% range) | Model 2 | recalls |", "|---|---|---|---|---|---|---|"]
    for r in ok[:30]:
        lines.append(f"| {r['plate']} | {r['make_en']} | {r['year']} | {r['fuel']} | {r['est_km']:,} ({r['range'][0]:,}-{r['range'][1]:,}) | {'covered: ' + ', '.join(f'{k} {v}' for k, v in r['bands'].items()) if r['covered'] else 'not covered'} | {r['recalls']} |")
    (HERE.parent / "docs").mkdir(exist_ok=True)
    (HERE.parent / "docs" / "E2E_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (HERE.parent / "docs" / "e2e_results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(lines[:12]))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
