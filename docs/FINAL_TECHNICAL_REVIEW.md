# Final technical review (focused on concrete problems found in the source code)

Date: 2026-11-19. Scope: `backend/app/ml/mileage.py`, `backend/app/ml/risk.py`, the Model 1 to Model 2 integration, `backend/app/api/v1/records.py` (security), the dashboard wording and Hebrew fields. No dataset research, no new model, **no retraining**: the XGBoost boosters of both models are byte-for-byte the ones approved before. Commits: `ede4efd` (snapshot before the review) and the commit that carries this report (after the corrections).

Every number below comes from a script in `ml/src/` (result files in `ml/*.json`) or from the test suites; the scripts only read.

## 1. Model 1 (`mileage.py`)

**Why only age + fuel (+ ownership calibration).** Because it is all that is both *available for an Israeli plate* and *useful in the evidence*. The registry gives make, model, year, fuel and ownership, but no engine size, transmission or odometer. In the training markets (UK, India) make and model were tested in notebook 01 (no measurable value) and again now with the leave-one-market-out protocol of `model1_vs_cbs.py` (`ml/src/model1_make_experiment.py`; RMSE in km after age-band calibration):

| Target market | age + fuel (production) | + make | + make and model |
|---|---|---|---|
| UK | 25,032 | 29,121 (worse by 16%) | 27,791 (worse by 11%) |
| India | 31,993 | 31,617 (better by 1.2%) | 31,313 (better by 2.1%) |
| US | 77,742 | 75,793 (better by 2.5%) | 74,271 (better by 4.5%) |

The effect changes sign between markets, so there is **no evidence that make or model personalise the estimate for a different market**; nothing was changed. The ownership factor is the only per-vehicle information with official Israeli backing (CBS Publication 1923). The model is a population-level estimate and is presented as such.

**Calibration curve: a real inconsistency, fixed.** `ml/src/model1_curve_audit.py` showed that the tree model spends kilometres in steps and the age-band factor then amplified them: the calibrated yearly increment of a petrol car was **800 km at age 8 and 15,400 km at age 9**, a hybrid had **84,600 km in a single year (age 11)**, a diesel 2,600 km at age 13. The cumulative estimate stayed monotone, but neighbouring ages could get almost the same estimate or jump. Fix (`smooth_cumulative` in `mileage.py`, applied at load time; factors recomputed by `ml/src/model1_smooth_calibration.py`): a 3-year centred moving average of the yearly increments, total at the supported age preserved. Boosters untouched. Effect (windows 1 / 3 / 5 compared in the script, 3 chosen as the smallest that removes the steps):

| | before | after (3 years) |
|---|---|---|
| smallest calibrated yearly increment (ages 1 to 16, all fuels) | 791 km | 9,545 km |
| largest jump over the previous year | 19.4 times | 1.9 times |
| error on the CBS Table-8 joint cells not used in the fit | 4.5% | 3.7% |
| in-sample R2 of the learned curve | 0.544 | 0.540 |

**Electric vehicles.** No training data (about 12 rows) and no CBS figure: the petrol curve is used, and the API says so in `notes` ("electric vehicle: petrol curve used"). Confirmed identical to petrol for ages 0 to 29 (so the estimate of an electric car is *not* individualised at all). Model 2 declines electric vehicles.

**Very old vehicles.** Above age 13 the training data carry no information (the learned curve is flat) and the official CBS yearly rate of the age band is used; above 45 the age is capped, with a note. Private petrol: 186,000 km at 13 years, 266,000 at 20, 357,000 at 30, 404,000 at 40, 427,000 from 45 (about 9,500 km per year at the end, the CBS rate of that band). On the 17,507 real registry vehicles aged 1 and older, 0.04% get more than 400,000 km and 0.4% more than 40,000 km per year; the largest estimate is 507,100 km. The extremes are combinations that hardly exist (diesel or hybrid under leasing or company ownership, 10 to 13 years old), where the product of the age factor (2.0) and the ownership factor (1.5 to 1.6) is highest. The hybrid curve at ages 8 to 12 (40,000 to 49,000 km per year) rests on few training rows and is the weakest part of the model. **Left as it is and listed as a limitation** (no data to correct it with, and inventing a cap would be inventing data).

**Uncertainty range.** Quantile models scaled by the same calibration ratio. Coverage of the nominal 80% range: 81.5% on held-out vehicles of the training markets and 89.6% (UK), 80.3% (India), 82.7% (US) when the model is applied to a market it never saw (`model1_vs_cbs_results.json`). Its width is 104% to 117% of the estimate for ages 4 to 19 and 148% for ages 0 to 3. The text shown to the user was shortened and says exactly this: indicative range, about 8 in 10 similar vehicles, not a measurement, not validated for individual Israeli vehicles. When a measured odometer exists it replaces the estimate (label "measured"), and the estimate is kept only for comparison.

## 2. Model 2 (`risk.py`)

**What each variant really uses** (read from `model2_card.json` and pinned by a test):

| Variant | Used when | Inputs |
|---|---|---|
| `cold` | registry only | vehicle age at the last inspection, fuel, make (60 makes, others grouped), standard 12-month interval |
| `cold_odo` | + measured odometer (typed by the user or on a stored inspection) | the above + odometer |
| `hist` | + result of the previous annual *inspection* stored for the vehicle | cold + defect found by system (brakes, electrical, engine-related) and any defect |
| `hist_odo` | both | everything |

The estimate of Model 1, the vehicle model name, the maintenance records, the colour and the ownership are **not** inputs.

**Why the model name is not used.** In-country it adds only AUC +0.005 to +0.010, it does **not transfer** from the UK to the Netherlands (brakes 0.6433 with the name against 0.6488 without; electrical 0.6694 against 0.6678; engine 0.7479 against 0.7523, notebook 06) and only 59% (UK) and 52% (NL) of the Israeli vehicles have a name spelled like one in the training data. Adding it would add complexity and a false impression of vehicle-specific knowledge.

**Are Low / Moderate / High still statistically correct?** Yes, nothing changed in the scale. The levels are positions among 660,202 out-of-sample UK reference scores; the defect rates observed at the next inspection rise with the level in both countries (UK brakes 3.0 / 6.4 / 12.0%, electrical 3.9 / 11.1 / 21.3%, engine-related 1.0 / 2.6 / 6.1%; NL 4.5 / 6.6 / 13.5, 9.6 / 16.2 / 30.4, 0.6 / 1.5 / 5.8), and `test_levels_are_grounded_in_observed_defect_rates` checks the order. They are relative levels, never probabilities.

**Coherence for Israeli vehicles of different ages** (13,554 covered vehicles of the registry sample, scores only, `ml/src/model2_coherence_audit.py`): the level rises with age as it should (Spearman between age and score 0.89 brakes, 0.92 electrical, 0.93 engine-related). Brakes: ages 3 to 5: 96% Low; 6 to 8: 29 / 66 / 5%; 9 to 11: 2 / 43 / 55%; 12 to 14: 0 / 23 / 77%; 15 to 20: 96% High. **The consequence to explain in the defence:** because the reference is *all ages*, the main level is mostly an age effect (a 4-year-old is almost always Low, a 16-year-old almost always High); the information that separates vehicles of the same age is the *complementary same-age label* (lower / typical / higher), which is why both are shown.

**Unknown makes and vehicles outside the coverage.** 98.9% of the covered vehicles have a make that exists in the training makes; 1.1% (for example Chery) are grouped as "other makes" and the response carries the note "less evidence". The level of a vehicle with a *known* make would change in 27% to 46% of the cases if the make were unknown, so the make matters; for the unknown makes the result is therefore less certain, which the note says. Vehicles outside the coverage (fuel not petrol, diesel or hybrid; under 3 or over 20 years at the last inspection) get **no estimate at all** and a plain reason; the other panels (maintenance rules, recalls, mileage) remain. They are 29.4% of the registry sample (25.3% under 3 years old).

## 3. Integration: is the Model 1 estimate an input of Model 2?

The SRS (6.2) says so. **In the code it is not**, and that is the intended and documented architecture (change C24 in `SRS_v2.md`):

* `services/features.risk_inputs` builds `RiskInputs(age_year, fuel, make, previous, odometer_km)`; there is no field for an estimate. `services/prediction.py` passes an odometer to Model 2 **only** when it was measured (request or a stored inspection of the registry's last test).
* Experiments: the Model 1 estimate changed AUC by at most 0.002 (notebook 04) and between -0.001 and +0.001 (notebooks 07 and 09); a measured odometer adds +0.013 to +0.016.
* Two tests now pin it: `test_model2_has_no_input_from_model1` (the input class and the feature list of every variant) and `test_model1_estimate_does_not_change_the_model2_risk` (triples the Model 1 output in the running pipeline and requires an identical Model 2 response).
* The two stages still form one pipeline: Stage 1 (mileage, shown with its range) and Stage 2 (risk) in one request, and Stage 2 benefits from the *measured* odometer when it exists. No artificial connection was forced.

## 4. Security of the records (`records.py`)

**Risks confirmed in the code.** (a) `POST /maintenance` and `/inspections` accepted anything from anyone; an *inspection result is an input of Model 2*, so anyone could change the risk shown for somebody else's vehicle, or bury a vehicle's recommended-maintenance status. (b) A first record for an unknown plate created the vehicle row; two simultaneous first records raised an unhandled `IntegrityError` (HTTP 500). (c) No limit on the number of records, no date validation (future, year 1900, before the vehicle was built). (d) CORS `*`. (e) `docker-compose.yml` published PostgreSQL and Redis (default credentials) on all network interfaces. (f) The chat endpoint, which can cost an OpenAI request per call, had no limit.

**Solution chosen** (the simplest that is safe enough for an academic project and keeps the SRS "no user login"): reading stays open; **writing needs a shared workshop key** (header `X-Write-Key`, setting `RECORDS_WRITE_KEY` in the git-ignored `.env`; constant-time comparison; if no key is configured, writing is disabled; the key is never echoed or logged). Around it: per-address rate limit on writes (60 per minute, keyed first so wrong keys are throttled too) and on the chat (15 per minute); at most 300 maintenance records and 60 inspection results per vehicle; dates cannot be in the future, before 1950 or before the manufacture year; CORS restricted to the dashboard origins; all four published ports bound to `127.0.0.1`; the race on the first record handled. The dashboard asks for the key in a field kept in `sessionStorage` only. Seed, e2e and visual scripts read the key from `.env` and never print it. Demo and tests are preserved: the test suites run with a test key and generous limits, `test_security.py` (9 tests) checks refusal without / with a wrong key, no key configured, no vehicle row created by a refused request, dates, quota, rate limits (including key guessing and the chat) and CORS.

**What this does not give:** the key proves "an authorised workshop", not who wrote a record, and whoever holds it can write for any plate; there is no HTTPS, audit trail or key rotation, and the records are not verified against an official source. This is stated in `LIMITATIONS.md`.

**Secrets in repositories and shared ZIPs.** `.env` (local, 8+ variables) is git-ignored and untracked; the only tracked secret-like file is `.env.example`, which holds the development defaults of PostgreSQL (`smartcar`) and an empty `RECORDS_WRITE_KEY`; no key-like string (for example `sk-...`) exists in the tracked files or in the history scanned. The risk is **zipping the folder by hand**, which would include `.env`. Mitigation: `.gitignore` now also covers `.env.*`, `*.pem`, `*.key`, `*.zip`; `scripts/make_share_zip.py` builds the ZIP from tracked files only (`git archive`), refuses a dirty tree and checks the archive for secret-looking names. No secret value appears in this report or in any log.

## 5. Dashboard

* "Last MOT test" (British) became **"Last annual test (date)"**, with the line "The registry publishes the date of the last annual test, not its result", so nothing suggests official results exist.
* The vehicle card is split in two labelled blocks: **"Official registry data · Ministry of Transport"** and **"Mileage · machine-learning estimate (Model 1)"** (or "Odometer · entered by a workshop" when measured). The service log says "Manual records, not official data", demo rows carry a `DEMO` badge, and the risk and recall panels already carried their own kind labels.
* **Hebrew fields.** Audited on 19,200 real passenger vehicles (`ml/src/registry_hebrew_audit.py`): fuel and ownership 0% Hebrew; **colour 100% Hebrew** (91 distinct values), translated word by word (all 91 values, 100% of the vehicles, covered by a test with the unknown-word fallback "show as published"); manufacturer 0.4% Hebrew (20 spellings): the unambiguous ones were added (for example Audi written "אודי", Dodge, Maserati, Lotus); the model name (0.09% Hebrew) and the trim level (0.01%) are published names and are left as published. A side effect: vehicles whose make was a missing spelling of a training make (Audi) now reach Model 2 with the right make instead of "other makes".
* Text reduced where it did not carry information: the mileage label went from three sentences to two; the repeated "synced from PostgreSQL" line was dropped. No redesign. Checked at desktop (1280) and phone (390) width, light and dark, with screenshots that were looked at (`docs/screenshots/`).

## 6. Classification

**Critical (fixed).** Open writes to a Model 2 input (4); open chat cost (4); published database and Redis ports with default credentials on all interfaces (4); CORS `*` on a write API (4).
**Important (fixed).** Staircase in the calibrated mileage curve (1); British wording that could suggest official results (5); colour 100% in Hebrew and manufacturer spellings missing (5); HTTP 500 on simultaneous first records, unbounded and implausible records (4); SRS divergence on the Model 1 to Model 2 link implicit (3); `.env.*` and ZIP hygiene (4).
**Optional / future (not done).** Per-user accounts and an audit trail; HTTPS and key rotation; hybrid curve ages 8 to 12 and extreme leasing / company combinations (needs data); individual-level mileage accuracy in Israel (needs odometer data); make-specific effects for brakes (transfer UK to NL is partial); a validated Israeli inspection dataset (request to the Ministry); live OpenAI call not exercised (no key in this environment); real phones and browsers other than Chrome not tested; the old files `ml/models/*.joblib`, `train_regression.py`, `train_classification.py` of the first attempt are still in the repository, marked obsolete.

## 7. Tests run

| Suite | Result |
|---|---|
| Backend pytest (real PostgreSQL and Redis; government services replaced by recorded real rows) | **111 passed** (84 before; +9 security, +2 independence of the models, +16 translation: colours and manufacturers) |
| End-to-end, 88 real Israeli plates against the running stack (live data.gov.il), including the write refusals and CORS | **1,573 checks, 0 failures**; latency median 0.48 s cold, 32 ms cached |
| Browser check (headless Chrome 157, desktop and phone, light and dark) including the key refusal in the form | **111 / 111** assertions; screenshots looked at |
| Frontend type check (`tsc --noEmit`) | clean |
| Model checks (read-only scripts) | Model 1 curve audit, make experiment, plausibility, vs CBS; Model 2 coherence; Hebrew audit |

## 8. Remaining limitations and divergences from the original SRS (for the academic explanation)

1. **Model 1 does not feed Model 2** (C24): decided by evidence, pinned by tests.
2. **Model 2 predicts "defect at the next annual inspection", not "failure"**, trained on UK MOT and validated on Dutch RDW; it has not been validated on Israeli vehicles, and is shown as three relative levels, not as a probability (C5, C21 to C23). The SRS 90% failure threshold does not exist; the anomaly vehicle trips a maintenance *rule* (C9).
3. **Model 1 is a population-level estimate** calibrated to CBS statistics; its individual accuracy in Israel is unknown (no open odometer data) and it performs like an age-band lookup (RMSE between 0.8% better and 2.4% worse than the lookup in three markets), which is why it is never presented as a measurement.
4. **No user login** (SRS) but a shared workshop key for writing (C26).
5. **Smoothing of the learned curve** (C25): a post-processing change, boosters not retrained.
6. The API-Ninjas call of the SRS was not implemented (C12); the registry itself provides the data.
7. Model 2 declines about 29% of the Israeli fleet (new, electric, gas, very old) with an explanation, instead of guessing.

## 9. Presentation checklist

- [ ] `.env` has `RECORDS_WRITE_KEY`; `docker compose up`, `alembic upgrade head`, `python scripts/seed_demo.py`; open http://localhost:3000 (key typed in the field only for the live record demo).
- [ ] Flush Redis before the demo if cold latency is to be shown (`docker compose exec redis redis-cli FLUSHALL`).
- [ ] Show in this order: covered car without history (4908732) → same car with a measured odometer → car with history (6224652, DEMO badges) → anomaly (19319001, a rule, not a probability) → open recall (1169762) → electric car declined (88328404) → chat.
- [ ] Say once, clearly: official data / ML estimate / rule / manual record are four different things; the level is relative, not a probability; not validated for Israel.
- [ ] Be ready for: why the Model 1 estimate does not feed Model 2 (section 3); why not use make and model (sections 1 and 2); why the level is mostly age (section 2); what the workshop key does and does not protect (section 4).
- [ ] Keep `docs/FINAL_TECHNICAL_REVIEW.md`, `FINAL_REPORT.md`, `MODEL_CARDS.md`, `LIMITATIONS.md` open; share the project with `scripts/make_share_zip.py`, never by zipping the folder.

## 10. Addendum (second pass): hybrids, Model 2 against age alone, demo security

**Hybrids aged 8 to 12 (Model 1).** `ml/src/model1_hybrid_audit.py`: the training data hold **5, 4, 5, 4 and 2 hybrid vehicles** at ages 8 to 12 (21 in total, all UK listings; the first 8 years have 72 to 802 per age). The learned curve jumps there (+41,600 km in the step at age 11, from 4 vehicles), and the CBS age-band factors (3.4 for ages 7 to 9, 2.2 for 10 to 13), fitted on a fleet that is mostly petrol, multiplied the steps into 28,000 to 46,000 km per year. **The cause is the data, amplified by the calibration**: the CBS itself says 21,100 km per year for hybrids, and 14,200 and 12,600 for those age bands. Correction: fuels with fewer than 30 training vehicles at an age continue with the yearly growth of petrol vehicles above their last supported age (hybrid and LPG/CNG: 7), and the estimate is flagged **low reliability** in the API (`estimate_reliability`) and in the dashboard; electric vehicles (about 12 training rows) and estimates implying more than 40,000 km per year (more than the highest published group average, 28,400 km) are flagged too. Result for hybrids aged 8 to 12: 11,600 to 14,900 km per year. Held-out CBS joint-cell error 3.7% to 3.6%; the boosters were not retrained. 7.6% of the registry sample is flagged. Tests: `test_model1_flags_low_reliability_...`, `test_model1_flags_estimates_that_imply_...`, `test_low_reliability_mileage_is_passed_to_the_language_model_as_such`.

**Model 2 against an age-only baseline.** Nothing retrained; same test sets (UK out of sample, NL independent). Full tables: `docs/MODEL2_VS_AGE_BASELINE.md`. Short version: age alone gives AUC 0.64 to 0.72; the registry-only model adds +0.021 to +0.031 (UK) and +0.005 / +0.015 / +0.019 (NL: brakes / electrical / engine-related); with history +0.024 to +0.063; with history and odometer up to +0.083 (UK). Recall at 31% flagged: +2.7 to +3.8 points registry-only in the UK (none for brakes in the NL), +6.6 to +11.2 points with history and odometer. **Conclusion: a modest, real improvement over age, small for registry-only brakes.** The risk panel now says so in its details.

**Write key, frontend included.** The key is not in any file served to the browser (6 files scanned), not in the backend logs, not in git or the reports (0 matches); it exists only in `.env`, in the backend container, and in the field the user types (a password field, `sessionStorage` of the tab). **Found and fixed:** the frontend container received the whole `.env` (key, database password) as environment variables although it needs only the public API address; now only `NEXT_PUBLIC_API_URL` reaches it. Residual risks: the key travels in a header over HTTP on `localhost` (no HTTPS); `sessionStorage` is readable by any script of the page (there is no third-party script); the field is masked on screen.

**OpenAI.** `docs/OPENAI_SETUP.md` and `scripts/check_openai.py` (they never print the key). The plate is no longer sent to the language model (data minimisation). The live call was not exercised here (no key).

Tests after the second pass: 115 pytest, 88 plates and 1,736 end-to-end checks, 133 browser assertions (`TEST_REPORT.md`).


## 11. Models rebuilt exactly as Smart_Car_Models.pdf specifies (2026-11-21)

At the student's request both models now follow the PDF exactly, with the data pulled from Kaggle (`kagglehub`). Full report generated from the results:
[SPEC_MODELS.md](SPEC_MODELS.md); change log C30 and C31 in `SRS_v2.md`.

* **Model 1:** XGBoost with Frequency encoding, chosen among Linear, Ridge (two scalers), Random Forest and XGBoost by cross-validated RMSE (22,155 km; held-out R² 0.609
  against 0.551 for the previous age + fuel model). Engine size and transmission at run time from the official model table (WLTP), number of owners from the ownership
  history. CBS calibration kept (held-out cell error 8.6%); above 40,000 km a year the official average for the age and ownership is shown instead, flagged.
* **Model 2:** XGBoost on Dataset 1 (+ Dataset 4 features), Dataset 5 model for electric / hybrid vehicles, scale_pos_weight chosen over SMOTE, Logistic Regression
  baseline, guarded Recall tuning, monotone constraints. ROC-AUC 0.978 on held-out Dataset 1 (synthetic) but **0.585 on real UK inspection outcomes, below age alone
  (0.646)**; Dataset 5 model 0.49 (chance). Shown as three levels with a per-vehicle note on what the level is worth; the real-inspection model stays as a comparison panel.
* Found while implementing: Dataset 1's third file is an augmented copy of the first (excluded); Dataset 8 `Owner_Type` is the number of owners; Dataset 4 has no age
  column; Dataset 1 requires Kaggle credentials for `kagglehub` (fallback: the earlier download of the same page).
* Security: the frontend container already no longer receives `.env`; nothing new is written by the new models.
* Tests: 135 pytest, 88 real plates with 1,995 end-to-end checks and 0 failures, 191/191 browser assertions.
