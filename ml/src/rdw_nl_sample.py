"""Pilot sample of the Dutch RDW open data (public domain): periodic technical inspections (APK) of passenger cars.

Why: it is a REAL-OUTCOME source (defects found per plate at each inspection), covering the whole Dutch fleet, with a vehicle
registry whose fields resemble the Israeli one (make, model, first-registration date, engine size, mass, fuel).
It contains NO odometer value (only a plausibility judgment), so mileage must be estimated (Model 1) as in Israel.

Sampling: plates whose LAST character is K (plate sequence cycles fastest in the last position, so this is ~1/20 of the fleet and
spread evenly over all registration years). Everything is fetched through the public Socrata API (no key), 50k rows a page.

Usage: python -I -X utf8 rdw_nl_sample.py [suffix=K]
"""
import json
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import INTERIM_DIR  # noqa: E402

B = "https://opendata.rdw.nl/resource/"
PAGE = 50000


def get(ds: str, params: dict, retries: int = 6):
    url = B + ds + ".json?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    for a in range(retries):
        try:
            out = subprocess.run(["curl", "-s", "-f", "-m", "120", "-A", "smartcar-ml-research", url],
                                 capture_output=True, timeout=140).stdout
            return json.loads(out)
        except Exception as e:  # noqa: BLE001
            print(f"  retry {a + 1} for {ds}: {type(e).__name__}", flush=True)
            time.sleep(2 + 3 * a)
    raise RuntimeError(f"giving up on {ds} {params}")


def pull(ds: str, select: str, where: str, out: Path, order: str = ":id") -> int:
    rows, off = [], 0
    while True:
        page = get(ds, {"$select": select, "$where": where, "$order": order, "$limit": PAGE, "$offset": off})
        rows += page
        print(f"  {ds}: {len(rows):,} rows", flush=True)
        if len(page) < PAGE:
            break
        off += PAGE
    out.write_text(json.dumps(rows), encoding="utf-8")
    return len(rows)


def main(suffix: str = "K") -> None:
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    k = f"kenteken like '%{suffix}'"
    reg_cols = ("kenteken,merk,handelsbenaming,voertuigsoort,inrichting,datum_eerste_toelating,datum_eerste_tenaamstelling_in_nederland,"
                "cilinderinhoud,aantal_cilinders,massa_ledig_voertuig,massa_rijklaar,catalogusprijs,taxi_indicator,export_indicator,"
                "eerste_kleur,aantal_zitplaatsen,tellerstandoordeel,jaar_laatste_registratie_tellerstand")
    print("registry (passenger cars)")
    pull("m9d7-ebf2", reg_cols, f"{k} AND voertuigsoort='Personenauto'", INTERIM_DIR / f"nl_registry_{suffix}.json")
    print("fuel")
    pull("8ys7-d773", "kenteken,brandstof_volgnummer,brandstof_omschrijving,nettomaximumvermogen", k, INTERIM_DIR / f"nl_fuel_{suffix}.json")
    print("inspections (light vehicles)")
    pull("sgfe-77wx", "kenteken,meld_datum_door_keuringsinstantie,soort_melding_ki_omschrijving,vervaldatum_keuring",
         f"{k} AND soort_erkenning_omschrijving='APK Lichte voertuigen'", INTERIM_DIR / f"nl_tests_{suffix}.json")
    print("defects found")
    pull("a34c-vvps", "kenteken,meld_datum_door_keuringsinstantie,gebrek_identificatie,aantal_gebreken_geconstateerd",
         f"{k} AND soort_erkenning_omschrijving='APK Lichte voertuigen'", INTERIM_DIR / f"nl_defects_{suffix}.json")
    print("defect catalogue")
    pull("hx2c-gt7k", "gebrek_identificatie,gebrek_omschrijving,gebrek_artikel_nummer,ingangsdatum_gebrek,einddatum_gebrek", "1=1",
         INTERIM_DIR / "nl_defect_catalogue.json")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "K")
