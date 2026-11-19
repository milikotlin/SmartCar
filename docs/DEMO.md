# Demonstration script (about 8 minutes)

Preparation (once): set `RECORDS_WRITE_KEY` in `.env`, then `docker compose up --build`, `docker compose exec backend alembic upgrade head`, `python scripts/seed_demo.py` (reads the key from `.env`). Open http://localhost:3000. To add a record live, type the workshop key in the "Workshop key" field of the service log (kept for the browser session only); without it the form refuses, which is also worth showing.
All plates are **real Israeli registrations**; the maintenance records and inspection results created by the seed script are demonstration data, labelled "[DEMO]".

## 1. The idea in one minute
"SmartCar-Ops takes a plate and shows three different things: an *estimated inspection-defect risk* (machine learning), *recommended maintenance* (rules) and *official recalls* (facts). They are never mixed, and nothing is presented as a probability validated for Israel."

## 2. A vehicle with no history (cold start) - plate `4908732`
* Registry profile live from data.gov.il, translated (Toyota Auris, 2015, petrol, private).
* **Estimated mileage with a range** (about 166,000 km, 80% range 76,000-268,000): Model 1, calibrated with official CBS statistics. Point out the label: *estimate, not a measurement*.
* **Risk bars:** each system has a level (Low / Moderate / High) on **one scale shared by every vehicle and age**: the further right, the higher the estimated risk that the next annual inspection finds a defect. Read the sentence "Higher than about N of 100 reference vehicles" (a rank, not a probability) and the complementary line, which compares only with vehicles of the same age. Open the details: how the levels were set and how often a defect was actually found in each level of the UK data.
* Maintenance rules: "No record" everywhere (nothing is invented); recalls: none.

## 2b. The case that motivated the new scale - Hyundai i20 2022 (plate `19202803`) against Nissan Micra 2014 (plate `9413531`)
Look both up one after the other. The i20 shows **Low** in all three systems; the Micra shows **Moderate** for brakes, **High** for electrical and **Moderate** for engine-related. The older car is estimated to be riskier on the same scale, and the same-age line explains that each is "about typical for its age". (Before the change the i20 showed a higher number than the Micra for brakes.)

## 3. A measured odometer changes the model - same plate
Type a measured odometer (for example 123456) in the box and press *Use this value*: the card switches to "Odometer (measured)", and the model details say that the *registry + measured odometer* variant is used. Explain: the Model 1 estimate is **not** fed to Model 2 because in every experiment it added nothing; a measured odometer does help (about +0.013 to +0.027 AUC).

## 4. History from the last inspection - plate `6224652` (seeded)
* Service log with [DEMO] records and the inspection result of the registry's last test: Model 2 uses the **history variant**; the note says the last inspection result is used. Add a new inspection result with a brake defect in the form and watch the brake gauge move (only an *inspection* result counts; a service record never becomes history).
* The brake rule says **no record, overdue**: a measured 194,000 km with no brake service on record.

## 5. The SRS anomaly vehicle - plate `19319001`
60,000 km measured, oil and tyres recorded, **no brake service**: the *brake rule* flags it (a rule, not an ML probability). This replaces the original "trips a 90% risk" scenario (change C9).

## 6. Official recall - plate `1169762` (Toyota 2007)
The open-recall panel lists the official category, type, date and the official Hebrew text. Stress: a recall is a fact, not a prediction.

## 7. A vehicle the model declines - plate `88328404` (electric)
"Not covered" with the reason (training data: petrol, diesel and hybrid cars 3-20 years old). The other panels still work.

## 8. Diagnostic chat
Open the chat, type "Hearing a squeaking noise when braking". Without an API key the answer is rule-based and says so; open "data used" to see the facts injected. With `OPENAI_API_KEY` set in `.env`, gpt-4o-mini answers using exactly those facts, forbidden from presenting the risk as a breakdown probability.

## 9. The evidence (slides or `docs/`)
* Why the original Dataset 1 was dropped (labels are rules, AUC 0.50) and what replaced it: real inspections from the UK (training) and the Netherlands (independent validation).
* `docs/MODEL_CARDS.md`: AUC, calibration, Logistic Regression benchmark, Dutch validation.
* `docs/UK_EXTRACTION.md`: CRC32-verified extraction and the decoder root cause.
* `docs/SRS_v2.md` section 11: every change against the original specification.
* `docs/LIMITATIONS.md`: what the system does not claim.

## Questions to expect
* *Why not predict breakdowns?* No open per-vehicle breakdown data with a denominator exists; the inspection defect is the closest real, validated event.
* *Why UK data for Israel?* Israeli inspection results are not open data; the system says so everywhere and proposes replacing the foreign data when the Ministry provides them.
* *Why does the mileage estimate not feed Model 2?* Measured: it adds no information beyond age and fuel; forcing it would be artificial.
* *Is XGBoost better than Logistic Regression?* Equal within noise (model cards); XGBoost is kept as required by the specification.
