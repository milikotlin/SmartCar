# Demonstration script (definitive, about 11 minutes)

All plates are **real Israeli registrations** (live data from data.gov.il). The maintenance records and inspection results of the seeded vehicles are demonstration data, shown with a `DEMO` badge. Every figure below was checked against the running system on 2026-11-19.

## A. Before the audience arrives (30 minutes before)

1. Docker Desktop running. `docker compose up -d`, then `curl http://localhost:8000/health` must answer `{"status":"ok"}`.
2. `.env` has `RECORDS_WRITE_KEY` (and, optional, `OPENAI_API_KEY`). **Never open `.env` on the shared screen.** Keep the workshop key in a password manager or on paper, and type it only in the key field (it is a password field).
3. First time on this machine: `docker compose exec backend alembic upgrade head`, then `python scripts/seed_demo.py` (reads the key from `.env`, takes about a minute).
4. Optional chat check: `python scripts/check_openai.py` (see `docs/OPENAI_SETUP.md`). Without a key the chat still works and says it is rule-based: both are fine to demonstrate.
5. **Warm the cache:** open each demo plate once (list below). The first call goes to data.gov.il (about half a second, sometimes slower); afterwards the answer is cached for 24 hours.
6. Browser: Chrome, 100% zoom, window maximised, dashboard at http://localhost:3000 in one tab and `docs/` open in another (this file, `MODEL_CARDS.md`, `MODEL2_VS_AGE_BASELINE.md`, `LIMITATIONS.md`).
7. **Plan B** if data.gov.il is down (the dashboard says "registry temporarily unavailable"): wait a minute and retry; cached plates still work; otherwise show `docs/screenshots/` (desktop and phone captures of every step) and say so.

## B. The script

| Time | Plate | What to do | What to say |
|---|---|---|---|
| 0:00 | (empty page) | Show the page | "SmartCar-Ops takes a plate and shows **three different things**, never mixed: an estimated inspection-defect risk (machine learning), recommended maintenance (rules) and official recalls (facts). The card also separates official registry data from the machine-learning estimate." |
| 1:00 | `4908732` | Search | Toyota Auris 2015, petrol, private. **Official registry block** (colour already translated; "last annual test (date)": the registry publishes the date, not the result). **Mileage block:** about 164,700 km, range 74,900-267,800: "an estimate for vehicles like this one, calibrated with official CBS statistics; the range is wide because individual cars differ a lot; not a measurement." |
| 2:30 | same | Risk panels (Model 2 first, then the comparison) | **Model 2 (PDF)**: Moderate, with the note "What this level is worth here" (no service log, so typical values). Open its details: the inputs and the ROC-AUC table (0.978 on its synthetic data, 0.585 on real UK inspections, age alone 0.646). Then the **comparison panel** (real inspections): three bars, all **Moderate** (Higher than about 65 / 70 / 50 of 100 reference vehicles). "One scale for every vehicle and age; it is a **relative level**, not a probability; not validated for Israeli vehicles." Open the details: how the levels were set and how often a defect was actually found in each level in the UK data; the line "most of the level reflects age". The complementary line compares only with cars of the same age. |
| 3:30 | same | In the mileage block choose **I know my car's mileage**, type `123456`, press **Use This Mileage** | The card shows **User-Reported Mileage** (tag USER-REPORTED: "not verified, not saved") and the risk panel uses the registry + odometer variant. Try `-5` or `abc` (clear message) and `900000` (shown but "not used by the risk model"). "A typed mileage is not a measurement; the **estimate of Model 1 is not an input** of Model 2: it added nothing in any experiment." Then choose **I don't know my car's mileage**: back to the AI-Estimated Mileage and the cold-start risk. |
| 4:30 | `19202803`, then `9413531` | Look both up | Model 2 (PDF): i20 2022 **Moderate**, Micra 2014 **Low**. Comparison model: i20 **Low, Low, Low**, Micra **Moderate / High / Moderate**. "This is why the comparison panel is there: the model trained on synthetic labels does not know that older cars fail more; the one trained on real inspections does." |
| 6:00 | `6224652` | Search | Seeded vehicle with `DEMO` records and the last inspection result: the variant that uses history and the measured odometer (**High, High, High**); the brake rule says **no record, overdue** (194,227 km measured, no brake service on record). Scroll to the service log: "manual records, not official data". |
| 7:00 | `4908732` | Service log: try to save an inspection result **without** the key | The form refuses: "Enter the workshop key first". Type a wrong key: "Missing or invalid workshop key". "Writing is reserved for authorised workshops, because a stored inspection result is an input of Model 2." |
| 7:45 | same | Type the real key, tick *Brakes* defect, save | The risk panel refreshes: variant with history; brakes move from Moderate to **High (about 95 of 100)**, electrical to High. "Only an annual **inspection** result counts as history; a service record never does." **After the demo remove it:** `docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DELETE FROM vehicles WHERE license_plate='"'"'4908732'"'"';"'` |
| 8:30 | `19319001` | Search | The SRS anomaly vehicle: 60,000 km measured, oil and tyres recorded, **no brake service**: the **brake rule** flags it. "A rule, not an ML probability; this replaces the SRS 'trips a 90% risk' scenario (change C9)." |
| 9:00 | `1169762` | Search | Open recall: the official category, type, date and Hebrew text. "A recall is a fact, not a prediction." |
| 9:20 | `88328404` | Search (Tesla Model 3, 2026) | Model 2 **declines** with the reason (fuel and age); the other panels work; the mileage block shows **Low reliability** (no electric training data). "I prefer to say 'no' than to guess." |
| 9:50 | `4850581` | Search (Mercedes GLC 350 e, hybrid, 9 years) | **Low reliability** box: "the training data hold too few hybrid vehicles older than 7 years"; estimate 163,100 km. "An earlier version produced 40,000 km per year here, from 4 or 5 training vehicles per age; now the system flags it and uses the growth of petrol cars." |
| 10:20 | any | Open the chat, type "Hearing a squeaking noise when braking" | Answer from the pipeline facts only (open "data used"); says whether it came from the language model or from the rule-based template. Not a diagnosis. |
| 11:00 | slides / `docs/` | Close | Limitations in one minute (below), then questions. |

## C. The one-minute limitations (say it yourself, before they ask)

* "Israeli inspection results are not open data. Model 2 learned from **UK** inspections and was validated on **Dutch** ones. I show relative levels, not probabilities, and I say it is not validated for Israel."
* "The target is a **defect found at the next annual inspection**, not a breakdown."
* "Most of the level reflects the vehicle's **age**. Compared with an age-only classification the model adds a modest part: small for registry-only brakes, larger for electrical and engine-related, and larger again when the previous inspection result or the odometer is known (`docs/MODEL2_VS_AGE_BASELINE.md`)."
* "The mileage is an estimate for a *type* of vehicle, not for this car, and the system flags the cases where the data cannot support it."
* "About 29% of the fleet (new, electric, gas, very old cars) gets no risk estimate, with the reason."

## D. Questions to expect

* *Why not predict breakdowns?* No open per-vehicle breakdown data with a denominator exists; the inspection defect is the closest real, validated event.
* *Why UK data for Israel?* Israeli inspection results are not open; the system says so everywhere and proposes replacing the foreign data when the Ministry provides them.
* *Why does the mileage estimate not feed Model 2?* Measured: it adds no information beyond age and fuel (change C24); forcing it would be artificial. The measured odometer does help and is used.
* *Is XGBoost better than a simple age rule?* Modestly (section "Limitations" above and `MODEL2_VS_AGE_BASELINE.md`); and equal to Logistic Regression within noise (`MODEL_CARDS.md`); XGBoost is kept as the specification requires.
* *Why not use the vehicle model name?* It does not transfer from the UK to the Netherlands and only about half of the Israeli vehicles have a name that exists in the training data.
* *What protects the records?* A shared workshop key, rate limits and checks; it is deliberately simple (no user accounts, as the SRS requires); see `LIMITATIONS.md`.
* *What if the OpenAI key is missing?* The chat answers from a rule-based template built from the same facts and says so.
