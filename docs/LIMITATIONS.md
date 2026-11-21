# Limitations of SmartCar-Ops (what the system does not do and what was not validated)

These limits are shown, in shorter form, in the interface and in the API (`disclaimer` and `provenance` fields).

## What the system does NOT claim

1. **It does not predict breakdowns.** Model 2 estimates the risk that the *next annual inspection finds a defect* in brakes, electrical system or engine-related items. No open data with real breakdowns, repair history and a denominator was found (NHTSA complaints have no vehicles without complaints; Irish, New Zealand and Czech sources are aggregated, absent or unverified).
2. **Its risk figures are not validated for Israel.** Model 2 was trained on UK MOT inspections and validated on Dutch RDW inspections. Israeli inspection results are not open data. The API and the dashboard therefore show only a **relative level (Low / Moderate / High) against UK reference vehicles of all ages**, plus a complementary comparison with vehicles of the same age; **no probability is shown**. Absolute rates differ between countries (for example electrical defects: 11% UK, 18% NL), while the order of risk replicates. The levels are positions in a ranking: the cut points (lowest 36% / next 33% / top 31% of the reference vehicles) come from UK data and the share of Israeli vehicles in each level is not guaranteed to be the same (in a registry sample of covered vehicles it is 30/28/42% for brakes, 34/28/39% for electrical and 42/26/32% for engine-related).
3. **Its discrimination is modest** (ROC-AUC about 0.67 to 0.80 depending on system and variant; precision 1.7 to 4.5 times the rate of flagging every vehicle, but low in absolute terms). It is a ranking, not a diagnosis.
4. **"Electrical" is mostly lighting and "engine-related" means emissions, fuel system and mounts**, because that is what the inspections record. It is not battery health or engine health.
5. **The mileage estimate is a population-level estimate**, calibrated with official CBS statistics by age band and ownership. It does not narrow the uncertainty of an individual vehicle: the range shown (about 80%) comes from the spread of used cars in the training markets and has not been validated on Israeli vehicles. Electric vehicles are treated like petrol vehicles (the CBS has no electric-vehicle data). Stacked effects (for example a diesel company car) are extrapolations.
6. **Maintenance recommendations are generic intervals**, not specific to a make and model; the owner's manual prevails. They are not learned from data.
7. **A recall is a fact published by the authority**, not a prediction; the system shows what the open-recall dataset contains for the plate at the time of the query.

## Coverage

* Model 2 covers petrol, diesel and hybrid vehicles that were 3 to 20 years old at their last annual inspection: **70.6% of a random sample of 19,200 Israeli passenger vehicles**. The 29.4% outside coverage are: **25.3% vehicles under 3 years old** (87% of them were last "tested" at registration: their first annual inspection has not taken place yet), **2.0% older than 20 years**, and **2.2% electric or gas vehicles aged 3 to 20** (7.1% of all vehicles are electric or gas, most of them new). For these the dashboard says why and still shows mileage, maintenance rules and recalls; it never invents a risk estimate. See [FINAL_REPORT.md](FINAL_REPORT.md) for the options to widen the coverage and why none is recommended now.
* Makes outside the 60 most common in the UK data are grouped as "other makes" (less evidence).

## Inputs and history

* The **history variants** use the result of the previous *annual inspection*, entered by the user. A maintenance record is **not** treated as an inspection result because that equivalence was not validated. Without an inspection result the cold-start variant (registry data only) is used.
* A **measured odometer** (entered by the user) improves the model by about 0.013 to 0.016 AUC. The mileage *estimated* by Model 1 is not a feature of Model 2 because it added no information in any experiment.
* The indicators are computed for a **standard interval of 12 months** to the next inspection; the planned interval of the plate is not used (it varied only with the timing of the test and did not improve the ranking).

## User-reported mileage

A mileage typed by the user is shown as **User-Reported Mileage**: it is not verified, not officially confirmed, and not saved. If it is plausible (at most 60,000 km per year of the vehicle's age) it is given to Model 2 as the odometer at the last inspection, an approximation, because it is the current mileage. A wrong but plausible value changes the risk level (a random error of 50% changes the level of about 15% of the vehicles). Details and evidence: `docs/MILEAGE_SELECTION.md`.

## Mileage estimate (Model 1): when it is flagged "low reliability"

The mileage block shows a **Low reliability** warning (field `estimate_reliability` of the API) when the training data cannot support the figure:

* **Electric vehicles** (no training data, no CBS figure): the petrol curve is used. Always flagged.
* **Hybrid and LPG/CNG vehicles older than 7 years**: the training data hold 2 to 5 vehicles per year of age (hybrids aged 8 to 12: 5, 4, 5, 4 and 2 vehicles, all UK listings). A previous version produced 35,000 to 46,000 km per year there: the tiny sample, multiplied by the CBS age-band factor (2.2 to 3.4) that was fitted on a petrol-dominated fleet. Now the curve of such a fuel keeps its own level up to age 7 and continues with the yearly growth of petrol vehicles (about 12,000 to 15,000 km per year); the figure is flagged.
* **Any estimate that implies more than 40,000 km per year**: the highest group average published by the CBS is 28,400 km (leasing cars). Such values appear only for combinations the CBS does not publish jointly (for example a diesel or hybrid car under leasing). The figure is shown, flagged.

On the 19,200 passenger vehicles of the registry sample 7.6% are flagged (6.8% electric, 0.4% hybrid or LPG/CNG over 7 years, 0.35% above 40,000 km per year); the other 92.4% are not affected (`ml/model1_reliability_share.json`).

## Model 2 compared with age alone

Most of the level reflects the age of the vehicle: age alone reproduces 85% to 97% of the discrimination (AUC above 0.5) of the registry-only model. The registry-only model adds AUC +0.021 to +0.031 over an age-only classification in the UK and only +0.005 (brakes), +0.015 (electrical) and +0.019 (engine-related) on the independent Dutch data; with the previous inspection result the gain is +0.024 to +0.063, and with the odometer as well up to +0.083 (UK). Details and Recall / Precision in `docs/MODEL2_VS_AGE_BASELINE.md`.

## Data and method

* UK data: a 1-in-41 sample of vehicles from the full 2022 and 2023 MOT files (the extraction was verified end to end with the CRC32 and size recorded in the zip files; see `docs/UK_EXTRACTION.md`). Pairs are an inspection in 2022 and the next inspection of the same vehicle in 2023.
* Dutch data: plates ending in the letter K (about 1 in 20 of the fleet); the open file of inspection notifications effectively starts in late 2023.
* Models were validated on vehicles never seen in training and on later dates; the Dutch validation is independent. XGBoost and Logistic Regression perform equally within the noise of the splits.
* The chat uses OpenAI gpt-4o-mini only when an API key is configured. The automatic tests use a mocked HTTP transport; the live OpenAI call was **not** exercised in this environment (no key available). Without a key the chat answers from a deterministic, rule-based template built from the same facts.
* The demonstration data (maintenance records and inspection results created by `scripts/seed_demo.py`) are generated and labelled "[DEMO]"; the 21 plates and their profiles are real.

## Operational

* **Security is deliberately simple** (no user accounts, as the SRS requires): reading is open; writing a record needs one shared workshop key, so the key proves "an authorised workshop", not who wrote the record, and anyone holding the key can write for any plate. Records are not verified against any official source. CORS accepts only the dashboard origin and the published ports are bound to the local machine; the system is not hardened for public internet exposure (no HTTPS, no per-user audit trail, no key rotation).
* The read endpoints are open: maintenance notes of a plate can be read by anyone who knows the plate (the plate itself is public registry data).
* Age is computed from the calendar year of the query; the calibration factors were fitted on a registry sample with ages as of 2026.
