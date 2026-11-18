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
| Estimated inspection-defect risk | Statistical estimate that the next annual inspection finds a defect in a system | Model 2 (XGBoost), UK/Dutch inspection data | Rank band against vehicles of the same age; probability only as a labelled reference figure |
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
| FR-5 (new) | Store maintenance records and annual inspection results | `POST/GET /api/v1/vehicles/{plate}/maintenance` and `/inspections`; tables `maintenance_records`, `inspection_records` |
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

Zone A: plate search. Zone B: vehicle card (estimated mileage with range, or measured), three risk gauges with a rank band (not a percentage of failure), recommended maintenance, official recalls, service and inspection history with forms. Zone C: chat widget. The interface states the origin of every figure.

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
| C2 | "Predict mechanical component failure probabilities" ("Brakes: 85% Failure Risk") | Estimated risk that the **next annual inspection finds a defect** in the system; shown as a rank among vehicles of the same age | No open per-vehicle breakdown data with a denominator exists; the inspection defect is the closest real, validated event. Probabilities are calibrated on foreign data and are not shown as validated for Israel |
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
