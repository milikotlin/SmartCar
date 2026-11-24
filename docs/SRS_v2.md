# SmartCar-Ops - Software Requirements Specification, version 2 (as implemented)

This document replaces `SmartCar-Ops_SRS.pdf` and the system specification (`SmartCar-Ops_מסמך_אפיון.pdf`) for the delivered system. Section 11 is the explicit **change log against the
original specification**: every requirement that changed, the reason, and the evidence. Numbers about the models are in [MODEL_CARDS.md](MODEL_CARDS.md) (generated from the exported artifacts),
tests in [TEST_REPORT.md](TEST_REPORT.md) and [E2E_REPORT.md](E2E_REPORT.md), limitations in [LIMITATIONS.md](LIMITATIONS.md).

## 1. System overview

SmartCar-Ops is a decoupled client-server analytical dashboard, without forced authentication, that takes an Israeli licence plate and returns, from real data:

1. the registry profile of the vehicle (Ministry of Transport, data.gov.il);
2. an **estimated mileage** with an uncertainty range (Model 1, calibrated with official CBS statistics);
3. an **estimated inspection-defect risk** for brakes, electrical system and engine-related items (Model 2);
4. **recommended maintenance** computed by rules from the vehicle's own service records;
5. **official open recalls** for the plate;
6. a **diagnostic chat** (OpenAI gpt-4o-mini with context injection, deterministic fallback).

The system keeps three kinds of statements strictly apart, in the API, the interface and the chat:

| Kind | What it is | Source | How it is shown |
|---|---|---|---|
| Estimated inspection-defect risk | Relative risk that the next annual inspection finds a defect in a system | Model 2 (XGBoost), UK/Dutch inspection data | Level Low / Moderate / High against all UK reference vehicles of any age (a rank, not a probability), with a complementary comparison with vehicles of the same age; no probability is shown |
| Recommended maintenance | Generic service intervals applied to the vehicle's own records | Rules (not learned) | Status per item (up to date, due soon, overdue, no record) |
| Official recall | A fact published by the authority | Ministry of Transport open data | List with category, type, date and the official text |

It never presents a risk as a probability of breakdown and never as a probability validated for Israel (no Israeli inspection outcomes exist in open form).

## 2. Functional requirements

| ID | Requirement | Implementation |
|---|---|---|
| FR-1 | Accept a 7 or 8-digit plate and query data.gov.il (CKAN, resource `053cea08-09bc-40ec-8f7a-156f0677aff3`) asynchronously | `GET /api/v1/vehicles/{plate}`; `services/gov_api.py`; Redis cache 24 h |
| FR-2 | Translate Hebrew registry values to English | `services/translation.py` (vocabularies verified on 20,000 real rows; unknown values are returned as published). The API-Ninjas call was **not** implemented (change C12) |
| FR-3 | Two-stage ML pipeline: Stage 1 estimates kilometres, Stage 2 estimates risk | Stage 1 `ml/mileage.py`; Stage 2 `ml/risk.py`; the Stage-2 input is a mileage value **with a flag** (measured or estimated) only where this improves the model (change C5) |
| FR-4 | Context-injected diagnostics with OpenAI gpt-4o-mini | `POST /api/v1/chat`; `services/chat.py`; deterministic fallback without a key or when the call fails |
| FR-5 (new) | Store maintenance records and annual inspection results | `POST/GET /api/v1/vehicles/{plate}/maintenance` and `/inspections`; tables `maintenance_records`, `inspection_records`. **Reading is open; writing needs the workshop key** (header `X-Write-Key`, change C26) |
| FR-6 (new) | Recommended maintenance from rules | `services/maintenance_rules.py` |
| FR-7 (new) | Official open recalls per plate | `services/recalls.py` (resource `36bf1404-0be4-49d2-82dc-2f1ead4a8b93`) |
| FR-8 (new) | Aggregated prediction | `GET /api/v1/predict/{plate}` (SRS section 6, step 1) |

## 3. Algorithmic and data constraints

* **Model 1** (regression): Datasets 7 + 8 + 3, XGBoost on age and fuel (monotone in age), calibration to the official CBS level by age band and ownership, output with an indicative 80% range.
* **Model 2** (classification): XGBoost per system on real inspection outcomes. Primary data UK MOT (verified full-year extraction), independent validation Dutch RDW. Logistic Regression benchmark and imbalance experiment were run; the natural objective is used. Evaluation by ROC-AUC, PR-AUC, capture in the top 20%, calibration error, and Precision/Recall/F1 at a threshold chosen on validation vehicles (never on test).
* **Sparsity management:** only features that exist for a real plate are used (age, fuel, make, planned interval, previous inspection result, measured odometer). No sensor feature exists in the training data.
* **No deterministic confidence fallback at 60%:** replaced by a coverage check and by showing rules and recalls as separate labelled sections (change C8).

## 4. Non-functional requirements

| ID | Requirement | Status |
|---|---|---|
| NFR-1 | Cache successful external retrievals in Redis, TTL 24 h | Done for the registry and the recalls |
| NFR-2 | Docker Compose: Python, PostgreSQL 15, Redis | Done; Python 3.13-slim instead of 3.11-slim (change C15) |
| NFR-3 | ML inference of the two stages at most 500 ms | Measured: see TEST_REPORT.md |
| NFR-4 | Backend strictly asynchronous (FastAPI/asyncio) | Done (httpx, SQLAlchemy asyncio, redis.asyncio); CPU-bound inference takes a few milliseconds |
| NFR-5 | 3NF database | Done: static `vehicles`; dynamic `maintenance_records` and `inspection_records` |

## 5. Architecture and data flow

```
Browser (Next.js 15, Tailwind v4)  --HTTP-->  FastAPI (async)  --->  Redis (24 h cache)
                                                    |   |------->  data.gov.il (registry, recalls)
                                                    |   |------->  PostgreSQL 15 (vehicles, maintenance_records, inspection_records)
                                                    |   `------->  OpenAI API (chat only)
                                                    `-- models loaded once at start-up from backend/app/ml/artifacts
```

`GET /api/v1/predict/{plate}`:
1. cache check, registry fetch, translation;
2. **Stage 1** - mileage estimate (age, fuel, ownership from the registry) with range; a measured odometer replaces it when known;
3. database join: records of the plate; the last **inspection** result is used only if it is the last annual test of the registry (within 60 days);
4. **Stage 2** - variant chosen from the available real inputs (`cold`, `cold_odo`, `hist`, `hist_odo`); coverage check;
5. rules and recalls; response with provenance.

## 6. Database schema

`vehicles` (static profile), `maintenance_records` (services and repairs) and `inspection_records` (result of an annual inspection by system, optional odometer; unique per plate and date).
Maintenance records are **not** treated as inspection results: the model was only validated on inspection results (approved decision).

## 7. API

| Method and path | Purpose |
|---|---|
| `GET /health` | Liveness |
| `GET /api/v1/vehicles/{plate}` | Registry profile (translated) |
| `GET /api/v1/predict/{plate}?odometer_km=` | Mileage, inspection risk, maintenance rules, recalls, history, provenance |
| `GET/POST /api/v1/vehicles/{plate}/maintenance` | Service records |
| `GET/POST /api/v1/vehicles/{plate}/inspections` | Annual inspection results |
| `POST /api/v1/chat` | Diagnostic chat (`license_plate`, `message`, optional `odometer_km`) |

Interactive documentation at `/docs`.

## 8. Interface

Zone A: plate search. Zone B: vehicle card (estimated mileage with range, or measured), three risk bars (brakes, electrical, engine-related) with the level Low / Moderate / High on one common scale, a complementary same-age line and plain-language explanations (see [RISK_SCALE.md](RISK_SCALE.md)), recommended maintenance, official recalls, service and inspection history with forms. Zone C: chat widget. The interface states the origin of every figure.

## 9. Machine learning (summary; details in MODEL_CARDS.md)

* **Model 1:** estimates population-level mileage for a vehicle class (age, fuel, ownership) calibrated to CBS Publication 1923. It does not narrow the uncertainty of an individual vehicle.
* **Model 2:** ranks vehicles by the risk that the next annual inspection finds a defect in a system. Discrimination is modest (ROC-AUC about 0.67 to 0.80); the model stays a ranking and not a diagnosis.
* **Mileage estimated by Model 1 is not used by Model 2:** in every experiment it added no information to age and fuel; a measured odometer does help and is used with a flag.

## 10. Testing

Unit and integration tests (pytest, inside the compose stack), model checks on the exported artifacts, golden predictions to detect environment differences, an end-to-end run with real Israeli plates against the live registry, and a front-end type check and production build. Results: TEST_REPORT.md and E2E_REPORT.md.

## 11. Change log against the original specification

| # | Original (SRS / specification / ML PDFs) | Delivered | Reason and evidence |
|---|---|---|---|
| C1 | Model 2 trained on Kaggle Dataset 1 (logistics maintenance history) | Trained on **UK MOT** inspections, validated on **Dutch RDW** inspections | Dataset 1 labels are deterministic rules and the runtime features give ROC-AUC 0.50 (notebook 02); Datasets 4 and 5 add nothing |
| C2 | "Predict mechanical component failure probabilities" ("Brakes: 85% Failure Risk") | Relative risk that the **next annual inspection finds a defect** in the system; shown as a level Low / Moderate / High among all reference vehicles (and, as complementary information, against vehicles of the same age); revised in round 5 (C21 to C23) | No open per-vehicle breakdown data with a denominator exists; the inspection defect is the closest real, validated event. Probabilities are calibrated on foreign data and are not shown as validated for Israel |
| C3 | Optimise heavily for Recall | ROC-AUC, PR-AUC, capture, calibration, Precision/Recall/F1 at a validation threshold | Recall alone is met by flagging every vehicle; the data support a ranking, not a screening cut-off |
| C4 | Class imbalance: SMOTE against `scale_pos_weight` | Both were tested; natural objective used | Natural objective keeps probabilities usable (notebooks 04-05) |
| C5 | Stage 2 features: age, **mileage from Stage 1**, days since last maintenance, brand reliability index | age, planned interval, fuel, make, previous inspection result, **measured** odometer | The Stage-1 estimate adds no information beyond age and fuel (paired bootstrap, three systems, two countries: notebooks 04, 07, 09); a measured odometer adds 0.013-0.016 AUC. Days-since-maintenance has no labelled data (used by the rules). Make is learned as a category instead of an external index |
| C6 | Dedicated EV model from Dataset 5 | Electric and gas vehicles are **not covered** by Model 2 (reason shown) | No real labels for them in the used data |
| C7 | Dataset 4 aggregation as features | Not used | Telemetry without real inspection outcomes |
| C8 | If XGBoost confidence is below 60% output a static rule-based schedule | Coverage check (fuel, age) plus **always-visible** rules and recalls, separately labelled | A classifier probability is not a confidence; rules are a complement, never a replacement |
| C9 | E2E anomaly vehicle (60,000 km, no brake replacement) trips a 90% risk threshold | The anomaly vehicle trips the **brake maintenance rule** | Risk scores are rank bands, there is no 90% failure probability |
| C10 | Model 1: encoding experiment, KNN imputer, algorithm comparison | Experiments done (notebook 01); final model XGBoost on age and fuel, make and engine size dropped | No measurable value from make or engine size; the Israeli registry has neither engine size nor transmission |
| C11 | Model 1 output a single value | Value **with an 80% range**, calibrated with **official CBS data** (age band x ownership) | The learned model alone implied about half of the official Israeli usage; the calibration fixes the level of population means (held-out CBS cells: see MODEL_CARDS.md); individual accuracy in Israel is unknown |
| C12 | API-Ninjas for transmission and curb weight (FR-2) | Not integrated | Neither feature improved any model in the experiments; engine size and mass changed AUC by at most 0.003 |
| C13 | Registry returns engine capacity | The registry resource has no engine capacity, mileage or transmission | Verified on 20,000 real rows |
| C14 | Models exported as `.joblib` | Native XGBoost JSON boosters plus JSON metadata | Portable across Python and library versions; the models were trained with the same versions that run in the image; golden-prediction tests guard the equivalence |
| C15 | Python 3.11-slim | Python 3.13-slim | The final libraries (numpy 2.5, xgboost 3.4) require Python 3.12 or newer and are the ones used for training |
| C16 | 8-digit plates | 7 or 8 digits | Israeli plates have 7 or 8 digits |
| C17 | Prompt shows ML risk scores as percentages | Prompt carries the three kinds of information separately and forbids presenting the risk as a breakdown probability | Honesty of the generative layer |
| C18 | Redis cache for the registry only | Also for the recalls | Same rate-limit reasoning |
| C19 | (not specified) | Inspection results table and endpoints; recalls; maintenance rules; CBS calibration; coverage check; provenance block | Needed to keep the three statements apart and to feed the history variants |
| C20 | Test strategy: Logistic Regression against XGBoost by recall | Done by AUC and the other metrics on the same split; they are equal within noise | Reported in MODEL_CARDS.md |
| C21 | (not specified) The risk indicator initially showed a percentile among vehicles of the same age | **Main indicator: three levels (Low / Moderate / High) against all UK reference vehicles of any age**; same-age comparison kept as a complementary line | The same-age number could not be compared between vehicles (Hyundai i20 2022: brakes 53-84; Nissan Micra 2014: 23-43, although the Micra has more than twice the estimated risk). The all-ages scale keeps the model's order, captures more defects (top 20%: 32-47% of defects against 24-32% within age) and is monotone in observed defect rates (RISK_SCALE_PROPOSAL.md, RISK_SCALE.md) |
| C22 | (not specified) | Level cut points **chosen from observed defect rates**: Low = lowest 36% of reference vehicles, Moderate = next 33%, High = top 31% | Maximum-likelihood three-level partition of the UK out-of-sample scores with at least 20% per level; the common cut points lose at most 1.8% of the optimum of any system; observed rates Low < Moderate < High in the UK and, independently, in the Dutch data |
| C23 | (not specified) The score used the planned interval to the next inspection from the registry | Score computed for a **standard 12-month interval**; no probability, "times the average" or exact percentile shown | The planned interval varied from 0.74 to 1.07 years for identical vehicles (timing in the cycle), moved the estimate by 19% to 29% and did not improve the out-of-sample ranking; fixing it changes AUC by at most about 0.002 |
| C24 | SRS 6.2: the Model 1 mileage estimate is an input of Model 2 | **Not connected, by decision.** Model 2 receives only registry data, the last inspection result and a *measured* odometer; the estimate of Model 1 is never an input (pinned by `test_model2_has_no_input_from_model1` and `test_model1_estimate_does_not_change_the_model2_risk`) | In every experiment (notebooks 04, 07, 09) the estimate added nothing to age and fuel (AUC change between -0.001 and +0.002, inside the noise), while a measured odometer adds +0.013 to +0.016. An artificial connection would add complexity and a false impression of dependence. The two models stay in one pipeline (Stage 1 shown to the user, Stage 2 uses the measured value when it exists) |
| C25 | (not specified) Model 1 calibrated curve | The learned age curve is **smoothed** (3-year moving average of the yearly increments, total preserved) before the CBS calibration; XGBoost boosters unchanged, not retrained (Model 1 card version 1.0.1) | The tree model produced steps: 800 km in one year of a petrol car, 84,600 km in one year of a hybrid, so neighbouring ages could get almost the same estimate or jump. After smoothing: smallest yearly increment 9,500 km, largest jump 1.9 times, error on the held-out CBS joint cells 4.5% to 3.7%, in-sample R2 0.544 to 0.540 |
| C26 | (not specified; SRS requires no user login) Open write endpoints | Writing records needs a shared **workshop key** (`X-Write-Key`, kept in `.env`, constant-time comparison; no key configured = writing disabled), per-address rate limit on writes and on the chat, per-vehicle quota, no future or pre-manufacture dates, CORS restricted to the dashboard, database/Redis/API/frontend ports bound to `127.0.0.1` | A stored inspection result is an *input of Model 2*: with open writes anyone could change the risk shown for somebody else's vehicle. No user accounts are introduced (SRS), the key identifies "an authorised workshop", not a person. See `docs/FINAL_TECHNICAL_REVIEW.md` |
| C27 | (not specified) Model 1 always shows a figure | Model 1 flags **low reliability** (API field `estimate_reliability`, warning in the dashboard) for electric vehicles, for hybrid and LPG/CNG vehicles older than 7 years (fewer than 30 training vehicles per year of age) and for estimates that imply more than 40,000 km per year; for those fuels the curve continues with the yearly growth of petrol vehicles above age 7 | Hybrids aged 8 to 12 had 5, 4, 5, 4 and 2 training vehicles; the CBS age-band factor (2.2 to 3.4, fitted on a petrol-dominated fleet) multiplied their steps into 35,000 to 46,000 km per year, while the CBS average for hybrids is 21,100. Now about 12,000 to 15,000 km per year, flagged. 7.6% of the registry sample is flagged |
| C28 | (not specified) Model 2 claimed only as a ranking | The comparison with an **age-only baseline** is documented (`docs/MODEL2_VS_AGE_BASELINE.md`): the model adds a modest part (AUC +0.02 to +0.03 registry only in the UK, +0.005 to +0.019 in the NL; +0.04 to +0.08 with history and odometer); the dashboard says that most of the level reflects age | Honest statement of the value added over the simplest classification |
| C29 | (not specified) The dashboard accepted a "measured odometer" typed by the user | The user **chooses** between "I know my car's mileage" (shown as **User-Reported Mileage**, unverified, not stored) and "I don't know" (**AI-Estimated Mileage**, Model 1, the default); the API distinguishes `user_reported`, `measured` (stored record) and `estimated`. Model 2 receives a plausible typed value as the odometer at the last inspection (a recorded inspection odometer always wins; implausible values and uncovered vehicles are not used); the Model 1 estimate is still never an input | A typed value is not a verified measurement and must not be presented as one. Sensitivity test: a typical error keeps 85% to 97% of the gain of a true odometer and never makes the ranking worse than no odometer (`docs/MILEAGE_SELECTION.md`) |
| C30 | Smart_Car_Models.pdf: Model 1 on Datasets 7+8+3 with OHE, Target vs Frequency encoding, KNN imputer (K=5), Linear/Ridge vs Random Forest/XGBoost chosen by RMSE/MAE | **Implemented exactly** (`ml/src/spec_model1.py`, data pulled from Kaggle with `kagglehub`); XGBoost with Frequency encoding chosen by cross-validated RMSE. Engine size and transmission at run time from the official model table (WLTP), number of owners from the ownership history. The CBS calibration, range and reliability flags are kept on top | Requested by the student (2026-11-21): follow the PDF exactly. Dataset 8 `Owner_Type` turned out to be the number of owners, not private/leasing as the PDF says: used as such. Details: `docs/SPEC_MODELS.md` |
| C31 | Smart_Car_Models.pdf: Model 2 on Dataset 1 (+ Dataset 4 aggregation; Dataset 5 model for electric/hybrid), Vehicle_Age, Days_Since_Last_Maintenance, Brand_Reliability_Index, mileage from Model 1, SMOTE vs scale_pos_weight, Logistic Regression baseline, Recall tuning | **Implemented exactly** (`ml/src/spec_model2.py`) and made the main risk panel, shown as three levels (no percentage). The model on real UK/Dutch inspections (C1, C2, C5) stays as a **comparison panel** with a ROC-AUC table. This reverses C1/C7 and, for this model only, C24 (Model 1 now feeds Model 2, as specified) | Requested by the student. Forced deviations: the augmented third Dataset 1 file is excluded (near-duplicates), leaky columns dropped, Dataset 4 grouped by mileage only (no age column), brand index computed from real UK inspection outcomes (no Kaggle dataset measures it), Recall tuning guarded against "flag everything". The labels are synthetic: the external check on real inspections is in `docs/SPEC_MODELS.md` |
| C32 | Model 1 and Model 2 performance (Smart_Car_Models.pdf): data augmentation, SMOTE, no over-fitting or leakage, better predictions for the user | **Version 3.0.0** (`ml/src/model1_train.py`, `ml/src/model2_train.py`). Original Kaggle datasets unchanged; 250,000 (Model 1) and 260,000 (Model 2) synthetic vehicles from sequential CART synthesis (`ml/src/synthesis.py`), used **only in training**; every choice on real validation vehicles, results on real test vehicles (UK MOT, Dutch RDW). Model 1 on real odometers: RMSE 67,855 -> 47,969 km, MAE 47,762 -> 34,711 km, R² 0.119 -> 0.560. Model 2 on real vehicles: Recall 0.447 -> 0.577, Precision 0.334 -> 0.432, ROC-AUC 0.567 -> 0.674 | Requested by the student (2026-11-24). Official vehicles as the source of the synthetic rows go beyond the datasets named in the PDF (documented addition); encodings, algorithms, experiments and metrics of the PDF are kept |
| C33 | C31: ROC-AUC 0.978 of Model 2 on Dataset 1 | **Withdrawn: data leakage** (`Maintenance_Type` and "days since maintenance > 180" encode the label). `Maintenance_Type` is no longer an input; unknown inputs stay unknown (masked training) instead of being read as zero; the score is calibrated on real vehicles and one Low / Moderate / High scale serves both branches; Dataset 4 rates are non-decreasing with mileage, so a new car is never riskier than an older one | Found while analysing the data for C32; reported because it corrects an earlier claim |
