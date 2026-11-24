# Languages (English / Hebrew) and Nearby Garages

Two additions to the dashboard. Nothing in `backend/app/ml`, `ml/` or `services/prediction.py` was changed: the models, their training, data, metrics and predictions are the same (proof in section 3).

## 1. Languages

**What the user sees.** A selector (English 🇬🇧 / עברית 🇮🇱) in the header. English is the default. Hebrew translates the whole interface and turns the page right-to-left; the vehicle, the typed mileage and the chat stay on the screen.
The choice is kept for one year in the cookie `smartcar-locale`; the server reads it, so the next visit arrives directly in the right language and direction.

**Where the texts are (one place each):**

| Texts | Place |
|---|---|
| Interface (330 texts) | `frontend/messages/en.json`, `frontend/messages/he.json`, read with `next-intl`. The compiler checks every key; `npm run check:i18n` fails on a missing key, a missing placeholder, an untranslated text or a text written in a component |
| Texts produced by the backend (levels, notes, reasons, rules, recalls, model comparison ...) | `backend/app/i18n/domain.py` |
| Chat | `backend/app/i18n/chat_texts.py` |

**How the backend is translated.** The pipeline runs in English as before. `app/i18n/localize.py` then copies the finished answer, replaces the texts and adds language-independent codes (`estimate_reliability_code`, `reason_codes`,
`odometer_basis_code`, `interval_months`, `interval_km`), which the dashboard uses instead of reading English words. A text it does not know is shown unchanged, never guessed. API: `?lang=en|he` on `/predict` and `/vehicles`, `lang` in the chat body.

* Registry values (make, fuel, ownership, colour) are shown in Hebrew **as published**; recall descriptions were already the official Hebrew text.
* **Chat:** answers in the selected language, whatever language the question is in. The language model receives exactly the same (English) facts; only the instruction "Answer in ..." differs. The rule-based answer uses the same data in both languages.
  Symptom words in Hebrew were extended so that a question in Hebrew reaches the same system as the same question in English.
* Not translated, on purpose: model and method names (XGBoost, KNN, ROC-AUC, MOT), the model name of the car, records typed by a person, and names and addresses of garages (the register publishes them in Hebrew only).

**To add a language:** a file in `messages/`, an entry in `frontend/i18n/config.ts`, and the same entries in the two backend files.

## 2. Nearby Garages (מוסכים קרובים)

**What the user can do.** Type or choose a city (English or Hebrew, tolerant to spelling: "Petah Tikva" = "PETAH TIQWA" = "פתח תקוה"), or press "Use my location"; filter by service and radius; see name, address, distance, services, phone, position on a map; open the
route in Google Maps or Waze; call; open reviews and hours on Google. Loading, no-result, error (with retry), refused-location and outside-Israel states exist. If the vehicle on the screen is electric or hybrid, a shortcut filters the garages licensed for it.

### 2.1 Which source, and why

| Option | Real garages in Israel | Cost / key | Verdict |
|---|---|---|---|
| **Ministry of Transport register** "מוסכים ומכוני רישוי" (data.gov.il, updated daily, CC BY) | All licensed garages: 5,508 (name, address, city, phone, licensed trades) | Free, no key, same service the project already uses | **Chosen as the list** |
| **OpenStreetMap** | Only 251 garage points for the whole country, 19 with opening hours | Free (ODbL) | **Chosen for geometry**: house numbers, streets, boundaries and the map; opening hours when the same business states them (5) |
| **Google Places API (New)** | Broad; the only source of ratings | Key and billing account. Rating and hours are "Enterprise" fields: 1,000 free calls a month, then 35 USD per 1,000 (price list seen on 2026-11-24; check it before activating). Content may not be stored | **Optional**, off without a key |
| Waze / Google Maps **links** | - | Free, no key | Used for the routes |

**Configuration needed: none.** The section works without any key. Optional: `GOOGLE_PLACES_API_KEY` in `.env` (restrict it to "Places API (New)"), which adds a "Rating and hours" button per garage. Without it every card links to the garage on Google Maps, where
ratings and hours are shown by Google itself. **The Google call was tested with simulated answers only; it was not run against the real service because no key is configured.**

### 2.2 Positions: exact, approximate or none

The register has no coordinates. `scripts/build_garage_geo.py` (run by hand; result `backend/app/data/garage_geo.json`, 540 KB) finds each published street and house number in OpenStreetMap, inside the boundary of the published city:

| Position | Garages of the register | Shown as |
|---|---|---|
| House number mapped | 721 | exact, "2.1 km" |
| Street mapped (nearest known number or middle of the street, at most 1.2 km long) | 2,363 | "≈ 2.1 km", "Approximate position on the street" |
| Not found (post box, unnamed industrial area, street unknown to OpenStreetMap) | 2,424 | listed with its address, **no distance, not on the map** |

Large cities are covered best (Herzliya 98%, Ra'anana 96%, Jerusalem 95%, Tel Aviv 89%); several Arab towns publish only a post box (Tayibe 2%, Nazareth 5%). Check: 15 garages also exist in OpenStreetMap with the same phone number; 13 lie within 0.75 km of the
computed position (10 within 0.1 km; some of these use the same mapped address, so the check is only partly independent), and 2 are far away (5.5 and 10 km), probably other branches with the same number. A position is used only while the register still publishes the same address; when the register changes, run the script again.

### 2.3 Honesty rules

* Only garages of the official register. No rating, hours or address is invented; a Google result is accepted only with the same phone number, or a similar name at the same place.
* A city search says that it is approximate (straight lines from the city centre). A GPS search sorts by the straight-line distance from the user; driving distance is left to Google Maps / Waze.
* Licences that do not concern a private car (forklifts, tractors, trucks only, licensing desks) are left out. The name of the professional manager and the company number in the register are not kept.
* If data.gov.il is down, the last copy (up to 30 days) is shown with its date; without a copy the section says that the register is unavailable.

### 2.4 Security, privacy and cost

* Keys stay in the backend; a Google error never reaches the browser. Daily limit of paid calls (`GOOGLE_PLACES_DAILY_LIMIT`, 30), counted in Redis; if the counter cannot be read, no call is made. Google content is not cached, carries its attribution and takes the place of the map.
* Redis: the register is stored 24 h (and a 30-day copy for outages). Rate limit: 90 requests per minute and client.
* GPS: asked only when the button is pressed and only with the browser's permission; rounded to about 10 m, sent in the request body (never in the address), used in memory, not stored, not logged, not sent to anyone else. GPS needs `https` or `localhost`.
* The map loads its images from openstreetmap.org, as any OpenStreetMap map does (that server sees the area viewed). Its tile policy is meant for light use: a public production site would need its own tile provider.

## 3. Verification (2026-11-24)

| Check | Result |
|---|---|
| Predictions before and after, 88 real plates x 2 situations, English | 174 of 176 identical. The other 2 are one plate for which data.gov.il gave no engine data in the first recording and gives it now (different input, same model) |
| English x Hebrew, same plates | Same numbers, levels and flags in all 176; no English text left |
| `pytest` | 230 passed (143 before) |
| `npm run check:i18n`, `tsc`, production build | OK |
| Browser, desktop and phone | 252 of 252 checks (80 new) |
| End-to-end, 88 real plates | 2,004 checks, 0 failures |

## 4. Files

New: `backend/app/i18n/` (4 files), `backend/app/services/garages.py`, `services/google_places.py`, `api/v1/garages.py`, `app/data/garage_geo.json`, `tests/test_i18n.py`, `tests/test_garages.py`; `frontend/messages/`, `frontend/i18n/`, `components/LanguageSwitch.tsx`,
`components/garages/` (5 files), `lib/format.ts`, `global.d.ts`, `scripts/check-i18n.mjs`; `scripts/build_garage_geo.py`, `scripts/visual_i18n_garages.py`.

Changed: the dashboard components (texts moved to the dictionaries, left/right replaced by start/end), `lib/api.ts`, `lib/mileage.ts`, `lib/types.ts`, `app/layout.tsx`, `app/page.tsx`, `app/globals.css`, `next.config.ts`, `package.json` (next-intl, leaflet);
`services/chat.py`, `services/translation.py` and `schemas/vehicle.py` (Hebrew colour), `schemas/prediction.py` (codes), `services/vehicle_lookup.py`, `api/v1/predict.py`, `vehicles.py`, `chat.py`, `main.py`, `config.py`, `.env.example`.

**Updating an existing installation:** two frontend packages were added, and Docker keeps the old `node_modules` volume, so use `docker compose up --build -V`.
