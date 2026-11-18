# Limitations of SmartCar-Ops (what the system does not do and what was not validated)

These limits are shown, in shorter form, in the interface and in the API (`disclaimer` and `provenance` fields).

## What the system does NOT claim

1. **It does not predict breakdowns.** Model 2 estimates the risk that the *next annual inspection finds a defect* in brakes, electrical system or engine-related items. No open data with real breakdowns, repair history and a denominator was found (NHTSA complaints have no vehicles without complaints; Irish, New Zealand and Czech sources are aggregated, absent or unverified).
2. **Its risk figures are not validated for Israel.** Model 2 was trained on UK MOT inspections and validated on Dutch RDW inspections. Israeli inspection results are not open data. The API therefore reports a **rank among vehicles of the same age** and keeps the foreign-calibrated probability as a labelled reference figure. Absolute rates differ between countries (for example electrical defects: 11% UK, 18% NL).
3. **Its discrimination is modest** (ROC-AUC about 0.67 to 0.80 depending on system and variant; precision 1.7 to 4.5 times the rate of flagging every vehicle, but low in absolute terms). It is a ranking, not a diagnosis.
4. **"Electrical" is mostly lighting and "engine-related" means emissions, fuel system and mounts**, because that is what the inspections record. It is not battery health or engine health.
5. **The mileage estimate is a population-level estimate**, calibrated with official CBS statistics by age band and ownership. It does not narrow the uncertainty of an individual vehicle: the range shown (about 80%) comes from the spread of used cars in the training markets and has not been validated on Israeli vehicles. Electric vehicles are treated like petrol vehicles (the CBS has no electric-vehicle data). Stacked effects (for example a diesel company car) are extrapolations.
6. **Maintenance recommendations are generic intervals**, not specific to a make and model; the owner's manual prevails. They are not learned from data.
7. **A recall is a fact published by the authority**, not a prediction; the system shows what the open-recall dataset contains for the plate at the time of the query.

## Coverage

* Model 2 covers petrol, diesel and hybrid vehicles, 3 to 20 years old at their last annual inspection. About 30% of Israeli passenger cars are younger than 4 years and 7% are electric or gas: for them the system says "not covered" and shows the other sections.
* Makes outside the 60 most common in the UK data are grouped as "other makes" (less evidence).

## Inputs and history

* The **history variants** use the result of the previous *annual inspection*, entered by the user. A maintenance record is **not** treated as an inspection result because that equivalence was not validated. Without an inspection result the cold-start variant (registry data only) is used.
* A **measured odometer** (entered by the user) improves the model by about 0.013 to 0.016 AUC. The mileage *estimated* by Model 1 is not a feature of Model 2 because it added no information in any experiment.
* The planned interval to the next inspection is taken from the registry (licence valid until minus last test) and falls back to one year.

## Data and method

* UK data: a 1-in-41 sample of vehicles from the full 2022 and 2023 MOT files (the extraction was verified end to end with the CRC32 and size recorded in the zip files; see `docs/UK_EXTRACTION.md`). Pairs are an inspection in 2022 and the next inspection of the same vehicle in 2023.
* Dutch data: plates ending in the letter K (about 1 in 20 of the fleet); the open file of inspection notifications effectively starts in late 2023.
* Models were validated on vehicles never seen in training and on later dates; the Dutch validation is independent. XGBoost and Logistic Regression perform equally within the noise of the splits.
* The chat uses OpenAI gpt-4o-mini only when an API key is configured. The automatic tests use a mocked HTTP transport; the live OpenAI call was **not** exercised in this environment (no key available). Without a key the chat answers from a deterministic, rule-based template built from the same facts.
* The demonstration data (maintenance records and inspection results created by `scripts/seed_demo.py`) are generated and labelled "[DEMO]"; the 21 plates and their profiles are real.

## Operational

* The backend allows any origin (CORS `*`) and has no authentication, as in the original design (open analytical dashboard); it must not be exposed publicly as is.
* Age is computed from the calendar year of the query; the calibration factors were fitted on a registry sample with ages as of 2026.
