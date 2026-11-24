"""Builds backend/app/data/garage_geo.json: localities (Hebrew / English names, centre) and the map position of the licensed garages. Run by hand, not at run time.

Sources (no key needed)
  * data.gov.il  - "מוסכים ומכוני רישוי" (Ministry of Transport, licensed garages, updated daily) and "יישובים" (official locality names and ITM coordinates);
  * OpenStreetMap (Overpass API, ODbL) - house numbers, streets, municipal boundaries and car-repair POIs of Israel.

The garage register has an address but no coordinates. The position comes only from an exact match of the published street (and house number) inside the published locality:
  house  = the house number itself is mapped;  street = the street is mapped (position = the nearest known house number or the middle of the street);  otherwise NO position.
Nothing is guessed: a garage without a position is still listed, with its address, and is not drawn on the map.

Usage:  python scripts/build_garage_geo.py --cache <folder for the raw downloads>
"""
import argparse
import collections
import json
import math
import re
import time
from datetime import date
from pathlib import Path

import httpx
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "backend" / "app" / "data" / "garage_geo.json"
CKAN = "https://data.gov.il/api/3/action/datastore_search"
GARAGES, LOCALITIES = "bb68386a-a331-4bbc-b668-bba2766d517d", "e9701dcb-9f1c-43bb-bd44-eb380ade542f"
OVERPASS = ("https://overpass-api.de/api/interpreter", "https://maps.mail.ru/osm/tools/overpass/api/interpreter")
AREA = '[out:json][timeout:280];area["ISO3166-1"="IL"][admin_level=2]->.a;'
QUERIES = {
    "addr": AREA + '(node(area.a)["addr:street"]["addr:housenumber"];way(area.a)["addr:street"]["addr:housenumber"];);out center tags;',
    "streets": AREA + 'way(area.a)[highway~"^(primary|secondary|tertiary|unclassified|residential|living_street|service|pedestrian|trunk|road|footway)$"][name];out center tags;',
    "adm8": AREA + "rel(area.a)[boundary=administrative][admin_level=8];out geom;",
    "repair": AREA + 'nwr(area.a)[shop~"^(car_repair|tyres)$"];out center tags;',
}
MAX_STREET_RADIUS_KM = 1.2          # a longer street without a known house number says too little about where the garage is
FALLBACK_LOCALITY_RADIUS_KM = 3.0   # localities without a municipal boundary of their own (villages inside a regional council)


# ---------------------------------------------------------------- downloads
def ckan(resource: str) -> list[dict]:
    rows, off = [], 0
    while True:
        r = httpx.get(CKAN, params={"resource_id": resource, "limit": 5000, "offset": off}, timeout=90).json()["result"]
        rows += r["records"]
        off += 5000
        if off >= r["total"]:
            return rows


def overpass(query: str) -> list[dict]:
    for attempt in range(6):
        for url in OVERPASS:
            try:
                r = httpx.post(url, data={"data": query}, timeout=300, headers={"User-Agent": "garage-map-student-script/1.0", "Accept": "application/json"})
                if r.status_code == 200 and r.json().get("elements"):
                    return r.json()["elements"]
            except (httpx.HTTPError, ValueError):
                pass
        time.sleep(60)
    raise RuntimeError("Overpass did not answer")


def load(cache: Path, name: str, fetch):
    f = cache / f"{name}.json"
    if f.exists():
        d = json.loads(f.read_text(encoding="utf-8"))
        return d["elements"] if isinstance(d, dict) else d
    d = fetch()
    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return d


# ---------------------------------------------------------------- geometry
def itm_to_wgs84(x: float, y: float) -> tuple[float, float]:
    """Israeli Transverse Mercator (EPSG:2039) -> WGS84 degrees (datum shift included)."""
    a, f = 6378137.0, 1 / 298.257222101
    e2 = f * (2 - f)
    lat0, lon0, k0, fe, fn = math.radians(31.7343936111111), math.radians(35.2045169444444), 1.0000067, 219529.584, 626907.39

    def arc(p):
        return a * ((1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256) * p - (3 * e2 / 8 + 3 * e2**2 / 32 + 45 * e2**3 / 1024) * math.sin(2 * p)
                    + (15 * e2**2 / 256 + 45 * e2**3 / 1024) * math.sin(4 * p) - (35 * e2**3 / 3072) * math.sin(6 * p))

    m = arc(lat0) + (y - fn) / k0
    mu = m / (a * (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    p1 = mu + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu) + (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu) + (151 * e1**3 / 96) * math.sin(6 * mu)
    ep2 = e2 / (1 - e2)
    c1, t1 = ep2 * math.cos(p1) ** 2, math.tan(p1) ** 2
    n1 = a / math.sqrt(1 - e2 * math.sin(p1) ** 2)
    r1 = a * (1 - e2) / (1 - e2 * math.sin(p1) ** 2) ** 1.5
    d = (x - fe) / (n1 * k0)
    lat = p1 - (n1 * math.tan(p1) / r1) * (d**2 / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * ep2) * d**4 / 24)
    lon = lon0 + (d - (1 + 2 * t1 + c1) * d**3 / 6 + (5 - 2 * c1 + 28 * t1) * d**5 / 120) / math.cos(p1)
    # Israel 1993 -> WGS84, 7 parameters (position vector)
    n = a / math.sqrt(1 - e2 * math.sin(lat) ** 2)
    X, Y, Z = n * math.cos(lat) * math.cos(lon), n * math.cos(lat) * math.sin(lon), n * (1 - e2) * math.sin(lat)
    sec = math.pi / 648000
    rx, ry, rz, s = -0.33077 * sec, -1.85269 * sec, 1.66969 * sec, 1 + 5.4248e-6
    X, Y, Z = -24.0024 + s * (X - rz * Y + ry * Z), -17.1032 + s * (rz * X + Y - rx * Z), -17.8444 + s * (-ry * X + rx * Y + Z)
    p = math.hypot(X, Y)
    la = math.atan2(Z, p * (1 - e2))
    for _ in range(5):
        nn = a / math.sqrt(1 - e2 * math.sin(la) ** 2)
        la = math.atan2(Z + e2 * nn * math.sin(la), p)
    return math.degrees(la), math.degrees(math.atan2(Y, X))


def km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km (works on arrays)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    h = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(np.asarray(lon2) - lon1) / 2) ** 2
    return 6371.0088 * 2 * np.arcsin(np.sqrt(h))


def rings(rel: dict) -> list[np.ndarray]:
    """Closed outer rings of a boundary relation, as (lat, lon) arrays."""
    todo = [[(p["lat"], p["lon"]) for p in m["geometry"]] for m in rel["members"] if m["type"] == "way" and m["role"] in ("outer", "") and m.get("geometry")]
    out = []
    while todo:
        cur = todo.pop()
        grown = True
        while grown and cur[0] != cur[-1]:
            grown = False
            for i, w in enumerate(todo):
                if w[0] == cur[-1]:
                    cur, grown = cur + w[1:], True
                elif w[-1] == cur[-1]:
                    cur, grown = cur + w[::-1][1:], True
                elif w[-1] == cur[0]:
                    cur, grown = w[:-1] + cur, True
                elif w[0] == cur[0]:
                    cur, grown = w[::-1][:-1] + cur, True
                if grown:
                    todo.pop(i)
                    break
        if len(cur) > 3:
            out.append(np.array(cur))
    return out


def inside(lat: np.ndarray, lon: np.ndarray, ring: np.ndarray) -> np.ndarray:
    y, x = ring[:, 0], ring[:, 1]
    y2, x2 = np.roll(y, -1), np.roll(x, -1)
    res = np.zeros(len(lat), bool)
    for a, b, c, d in zip(y, x, y2, x2):
        if a != c:
            res ^= ((a > lat) != (c > lat)) & (lon < (d - b) * (lat - a) / (c - a) + b)
    return res


# ---------------------------------------------------------------- names
def norm(s: str | None) -> str:
    s = re.sub(r"[\u0591-\u05C7]", "", s or "")
    s = re.sub(r"[\"'׳״`´’.*]", "", s)
    s = re.sub(r"[-־–,/()\\:]", " ", s)
    s = re.sub(r"יי+", "י", re.sub(r"וו+", "ו", s))
    return " ".join(s.split())


def skeleton(s: str) -> str:
    """Spelling without vowel letters inside words (הריקמה = הרקמה); used only when it is unique in the locality."""
    return " ".join(w[0] + re.sub(r"[יו]", "", w[1:]) for w in s.split() if w)


PREFIX = re.compile(r"^(רחוב|רח|שדרות|שדרת|שד|דרך|סמטת|סמ|כביש|ככר|מעלה)\s+")
NOISE = re.compile(r"\b(תד|ת ד|ד נ|דנ|מיקוד|א\s?ת|אזור תעשיה|אזור התעשיה|אז התעשיה|איזור תעשיה|איזור התעשיה|א תעשיה|א התעשיה)\b\s*\d*")
LOCALITY_ALIAS = {"תל חנן": "נשר", "לוד נמל תעופה": "לוד", "מכר": "גדידה מכר", "גדידה": "גדידה מכר", "פרדס חנה": "פרדס חנה כרכור", "כרכור": "פרדס חנה כרכור", "גבעת עדה": "בנימינה גבעת עדה",
                  "בני עי ש": "בני עיש", "נוה נאמן": "הוד השרון", "עארה": "ערערה", "צור יגאל": "כוכב יאיר", "מעוז ציון ב": "מבשרת ציון", "כסרא": "כסרא סמיע", "יאנוח": "יאנוח גת", "ימא": "זמר",
                  "עין הנצי ב": "עין הנציב", "מוסמוס": "מעלה עירון", "סאלם": "מעלה עירון", "זלפה": "מעלה עירון", "בית אריה עופרים": "בית אריה", "מישור אדומים": "מעלה אדומים", "גולס": "גוליס"}
# usual English spellings of the larger localities (the official list is a strict transliteration in capitals: "PETAH TIQWA")
ENGLISH = {"תל אביב יפו": "Tel Aviv-Yafo", "ירושלים": "Jerusalem", "חיפה": "Haifa", "ראשון לציון": "Rishon LeZion", "פתח תקוה": "Petah Tikva", "אשדוד": "Ashdod", "נתניה": "Netanya", "באר שבע": "Beer Sheva",
           "בני ברק": "Bnei Brak", "חולון": "Holon", "רמת גן": "Ramat Gan", "אשקלון": "Ashkelon", "רחובות": "Rehovot", "בת ים": "Bat Yam", "בית שמש": "Beit Shemesh", "כפר סבא": "Kfar Saba", "הרצליה": "Herzliya",
           "חדרה": "Hadera", "מודיעין מכבים רעות": "Modi'in-Maccabim-Re'ut", "נצרת": "Nazareth", "לוד": "Lod", "רמלה": "Ramla", "רעננה": "Ra'anana", "רהט": "Rahat", "ראש העין": "Rosh HaAyin", "הוד השרון": "Hod HaSharon",
           "גבעתים": "Givatayim", "קרית גת": "Kiryat Gat", "נהריה": "Nahariya", "עפולה": "Afula", "קרית אתא": "Kiryat Ata", "יבנה": "Yavne", "אום אל פחם": "Umm al-Fahm", "אילת": "Eilat", "נס ציונה": "Ness Ziona",
           "עכו": "Acre (Akko)", "אלעד": "El'ad", "טבריה": "Tiberias", "רמת השרון": "Ramat HaSharon", "כרמיאל": "Karmiel", "קרית מוצקין": "Kiryat Motzkin", "טיבה": "Tayibe", "נוף הגליל": "Nof HaGalil",
           "שפרעם": "Shefa-'Amr", "קרית ביאליק": "Kiryat Bialik", "קרית ים": "Kiryat Yam", "קרית אונו": "Kiryat Ono", "צפת": "Safed (Tzfat)", "אור יהודה": "Or Yehuda", "דימונה": "Dimona", "טמרה": "Tamra",
           "נתיבות": "Netivot", "סחנין": "Sakhnin", "מגדל העמק": "Migdal HaEmek", "באקה אל גרביה": "Baqa al-Gharbiyye", "אופקים": "Ofakim", "טירה": "Tira", "שדרות": "Sderot", "ערד": "Arad", "יהוד מונוסון": "Yehud-Monosson",
           "קרית מלאכי": "Kiryat Malakhi", "קרית שמונה": "Kiryat Shmona", "נשר": "Nesher", "מעלה אדומים": "Ma'ale Adumim", "ביתר עילית": "Beitar Illit", "מודיעין עילית": "Modi'in Illit", "יקנעם עילית": "Yokneam Illit",
           "טירת כרמל": "Tirat Carmel", "באר יעקב": "Be'er Ya'akov", "גדרה": "Gedera", "זכרון יעקב": "Zikhron Ya'akov", "בית שאן": "Beit She'an", "אריאל": "Ariel", "קרית טבעון": "Kiryat Tivon", "מבשרת ציון": "Mevaseret Zion"}


def locality_key(yishuv: str, known: dict[str, int]) -> str | None:
    k = norm(yishuv)
    k = LOCALITY_ALIAS.get(k, k)
    if k in known:
        return k
    return next((c for c in (k.replace("  ", " "), k.replace(" ", "")) if c in known), None)


def address_candidates(address: str, locality: str) -> list[tuple[str, int | None]]:
    """(street text, house number) candidates of a published address, most specific first."""
    s = norm(address)
    s = re.sub(r"(?<=[א-ת])(?=\d)|(?<=\d)(?=[א-ת])", " ", s)
    s = NOISE.sub(" ", " " + s + " ")
    s = " ".join(s.split())
    out: list[tuple[str, int | None]] = []
    for m in re.finditer(r"([א-ת][א-ת ]*?)\s+(\d{1,4})(?=\s|$)", s):
        words = m[1].split()
        if words and words[-1] == "מספר":
            words = words[:-1]
        for i in range(len(words)):
            out.append((" ".join(words[i:]), int(m[2])))
    plain = [w for w in s.split() if not w.isdigit()]
    for n in range(min(len(plain), 5), 0, -1):
        for i in range(len(plain) - n + 1):
            text = " ".join(plain[i : i + n])
            if len(text) >= 4 and text != locality:
                out.append((text, None))
    return out


def variants(street: str) -> set[str]:
    base = PREFIX.sub("", street)
    v = {street, base}
    if base.startswith("ה") and len(base) > 3:
        v.add(base[1:])
    return v


def street_of(text: str, index: dict, skel: dict) -> str | None:
    for t in (text, PREFIX.sub("", text), "ה" + PREFIX.sub("", text)):
        if t in index:
            return t
    k = skeleton(PREFIX.sub("", text))
    names = skel.get(k, set()) if len(k.replace(" ", "")) >= 3 else set()
    return next(iter(names)) if len(names) == 1 else None


def street_by_words(text: str, index: dict) -> str | None:
    """"שמוטקין" / "קוזושניר אברהם" -> "בנימין שמוטקין" / "אברהם קוזושניר": all the published words, in exactly one street of the locality."""
    words = set(PREFIX.sub("", text).split())
    if not words or max(map(len, words)) < 4:
        return None
    names = {PREFIX.sub("", n) for n in index if words <= set(n.split())}
    return next(iter(names)) if len(names) == 1 and next(iter(names)) in index else None


def phone(s: str | None) -> str:
    d = re.sub(r"\D", "", s or "")
    return ("0" + d[3:]) if d.startswith("972") else d


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", type=Path, required=True)
    cache = ap.parse_args().cache
    cache.mkdir(parents=True, exist_ok=True)
    rows = load(cache, "garages", lambda: ckan(GARAGES))
    loc_rows = load(cache, "loc_e970", lambda: ckan(LOCALITIES))
    osm = {k: load(cache, k, lambda q=q: overpass(q)) for k, q in QUERIES.items()}

    # ---- localities
    localities, by_key = {}, {}
    for r in loc_rows:
        he = " ".join((r["name_in_hebrew"] or "").split())
        if not r["X"] or not he:
            continue
        lat, lon = itm_to_wgs84(float(r["X"]), float(r["Y"]))
        code, k = int(r["symbol_number"]), norm(he)
        name_en = ENGLISH.get(k) or " ".join(w.capitalize() for w in (r["name_in_english"] or "").split())
        localities[code] = {"he": he.replace(" - ", "-"), "en": re.sub(r"-(\w)", lambda m: "-" + m[1].upper(), name_en), "official_en": " ".join((r["name_in_english"] or "").split()), "lat": round(lat, 5), "lon": round(lon, 5)}
        by_key[k] = code
        by_key.setdefault(k.replace(" ", ""), code)
        by_key.setdefault(norm(re.sub(r"\(.*?\)", "", he)), code)

    # ---- which municipality each mapped point belongs to
    def coords(e):
        c = e.get("center", e)
        return c["lat"], c["lon"]

    pts = {k: (osm[k], *np.array([coords(e) for e in osm[k]]).T) for k in ("streets", "addr")}
    member: dict[str, dict[int, np.ndarray]] = {k: {} for k in pts}
    centre_of: dict[int, tuple[float, float]] = {}
    for rel in osm["adm8"]:
        ref = rel["tags"].get("ref:IL:cbs", "").split(";")[0]
        code = int(ref) if ref.isdigit() and int(ref) in localities else by_key.get(norm(rel["tags"].get("name:he") or rel["tags"].get("name")))
        rr = rings(rel)
        if code is None or not rr:
            continue
        centre_of[code] = (float(np.mean([r[:, 0].mean() for r in rr])), float(np.mean([r[:, 1].mean() for r in rr])))
        for k, (_, la, lo) in pts.items():
            mask = np.zeros(len(la), bool)
            for r in rr:
                box = np.flatnonzero((la >= r[:, 0].min()) & (la <= r[:, 0].max()) & (lo >= r[:, 1].min()) & (lo <= r[:, 1].max()))
                mask[box] |= inside(la[box], lo[box], r)
            member[k][code] = np.flatnonzero(mask)

    # ---- garages
    by_id = collections.defaultdict(list)
    for r in rows:
        by_id[int(r["mispar_mosah"])].append(r)
    poi_by_phone = {}
    for e in osm["repair"]:
        for p in re.split(r"[;,/]", e["tags"].get("phone", "") + ";" + e["tags"].get("contact:phone", "")):
            if len(phone(p)) >= 9:
                poi_by_phone[phone(p)] = e

    cache_index: dict[int, tuple] = {}

    def locality_index(code: int):
        if code not in cache_index:
            idx = {}
            for k, (els, la, lo) in pts.items():
                if code in member[k]:
                    idx[k] = member[k][code]
                else:
                    c = localities[code]
                    idx[k] = np.flatnonzero(km(c["lat"], c["lon"], la, lo) <= FALLBACK_LOCALITY_RADIUS_KM)
            streets, houses = collections.defaultdict(list), collections.defaultdict(dict)
            els, la, lo = pts["streets"]
            for i in idx["streets"]:
                tags = els[i]["tags"]
                for n in {tags.get("name:he"), tags.get("name"), tags.get("alt_name:he"), tags.get("alt_name")} - {None}:
                    for v in variants(norm(n)):
                        streets[v].append((la[i], lo[i]))
            els, la, lo = pts["addr"]
            for i in idx["addr"]:
                num = re.match(r"\d+", els[i]["tags"]["addr:housenumber"])
                if num:
                    for v in variants(norm(els[i]["tags"]["addr:street"])):
                        houses[v].setdefault(int(num[0]), (la[i], lo[i]))
                        streets[v]          # a street known only from its house numbers is still a street
            for v in houses:
                if not streets[v]:
                    streets[v] = list(houses[v].values())
            skel = collections.defaultdict(set)
            for v in streets:
                skel[skeleton(PREFIX.sub("", v))].add(PREFIX.sub("", v))
            cache_index[code] = (streets, houses, skel)
        return cache_index[code]

    def locate(code: int, address: str):
        streets, houses, skel = locality_index(code)
        candidates = address_candidates(address, norm(localities[code]["he"]))
        found = [(street_of(text, streets, skel), number) for text, number in candidates] + [(street_by_words(text, streets), number) for text, number in candidates if number is not None]
        for st, number in found:
            if st is None:
                continue
            h = houses.get(st, {})
            if number is not None and number in h:
                return (*h[number], "house", 0.05)
            p = np.array(streets[st])
            if number is not None and h:
                near = min(h, key=lambda n: abs(n - number))
                if abs(near - number) <= 10:
                    return (*h[near], "street", 0.2)
            mid = np.median(p, axis=0)
            d = km(mid[0], mid[1], p[:, 0], p[:, 1])
            best = p[int(np.argmin(d))]
            radius = float(np.max(km(best[0], best[1], p[:, 0], p[:, 1])))
            if radius <= MAX_STREET_RADIUS_KM:
                return (best[0], best[1], "street", radius)
        return None

    garages, check, unmatched = {}, [], collections.Counter()
    for gid, rs in by_id.items():
        r = rs[0]
        key = locality_key(r["yishuv"], by_key)
        code = by_key.get(key) if key else None
        if code is None:
            unmatched[r["yishuv"]] += 1
        pos = locate(code, r["ktovet"] or "") if code is not None else None
        poi = poi_by_phone.get(phone(r["telephone"]))
        item = {"a": r["ktovet"], "c": code}
        if poi:
            la, lo = coords(poi)
            c = localities.get(code)
            if pos:
                check.append((float(km(pos[0], pos[1], la, lo)), pos[2], r["shem_mosah"], r["ktovet"], r["yishuv"]))
            # the same phone number AND the same place: the same business (a chain can publish one number for several branches)
            if c and (km(pos[0], pos[1], la, lo) <= 1.0 if pos else km(c["lat"], c["lon"], la, lo) <= FALLBACK_LOCALITY_RADIUS_KM):
                pos = (la, lo, "house", 0.03)
                if re.search(r"\d\d:\d\d|24/7", poi["tags"].get("opening_hours", "")):
                    item["h"] = poi["tags"]["opening_hours"]
        if pos:
            item.update({"lat": round(float(pos[0]), 5), "lon": round(float(pos[1]), 5), "p": pos[2], "r": round(pos[3], 2)})
        garages[gid] = item

    n = collections.Counter(g.get("p", "none") for g in garages.values())
    print("garages", len(garages), dict(n), "| localities", len(localities), "| no locality:", sum(unmatched.values()), unmatched.most_common(25))
    print("opening hours (OpenStreetMap):", sum("h" in g for g in garages.values()))
    print("independent check against OpenStreetMap POIs with the same phone (km):", sorted((round(c[0], 2), c[1]) for c in check))
    for c in sorted(check, reverse=True)[:5]:
        print("   ", c)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    meta = {"built": date.today().isoformat(), "garages_source": "data.gov.il, Ministry of Transport and Road Safety: licensed garages (CC BY)", "geometry_source": "© OpenStreetMap contributors (ODbL)",
            "positions": dict(n), "check_km": sorted(round(c[0], 2) for c in check)}
    OUT.write_text(json.dumps({"meta": meta, "localities": localities, "garages": garages}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(OUT, OUT.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
