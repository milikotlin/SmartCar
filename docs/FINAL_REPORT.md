# SmartCar-Ops: final readiness report

Scope of this round: coverage of Israeli vehicles, a complete visual check of the dashboard (desktop and phone), the real benefit of Model 1 over a simple CBS estimate, and the final flow tests.
**No model was retrained or changed.** Everything below was measured; where something could not be verified, it says so.

## 0. Verdict

| | |
|---|---|
| **Ready for the academic demonstration?** | **Yes**, with the limitations of section 6 stated openly (they are in the interface, the API and `docs/LIMITATIONS.md`). No blocking defect is known. |
| **Approved and working** | Registry lookup and translation; Model 1 estimate with range; Model 2 levels (Low / Moderate / High) with the same-age complement; maintenance rules; official recalls; records and inspection history; chat (deterministic fallback verified, OpenAI path verified with a mocked transport); covered and not covered flows; desktop and phone layout in a real browser. |
| **Corrected in this round** | 6 defects/clarity problems found by the checks (section 5). |
| **Not verified** | The live OpenAI call (no API key here); real phones, Safari and Firefox; screen readers; accuracy on Israeli vehicles (no open Israeli data exist). |

## 1. Coverage of Israeli vehicles

**Why 36 of the 88 plates were not covered.** The 88 plates were chosen to stress the system (they deliberately include 5 vehicles of age 0 to 2, 5 older than 21 years, 6 electric and 2 gas vehicles). Of the 36: **25 are under 3 years old** (20 of them petrol or diesel, 5 also electric), **7 are older than 20 years**, and **4 are electric or gas vehicles of an age within the range**. The coverage of that stress sample (59%) is therefore **not** the coverage of the fleet.

**Coverage of the real fleet** (random sample of 19,200 Israeli passenger vehicles from the registry): **70.6% covered**. The 29.4% outside:

| Reason | Share of the fleet | Why |
|---|---|---|
| Under 3 years at the last inspection | **25.3%** | In Israel the first annual test is at 3 years. 87% of these vehicles were last "tested" at registration (age 0), so the next inspection is their **first**. The model learns the defect at the *next* inspection of vehicles that already had one. |
| Older than 20 years | 2.0% | Too few vehicles of that age in the training data for a reliable estimate (UK and Dutch rates plateau and thin out above 17 years). |
| Electric or gas, age 3 to 20 | 2.2% | The inspection data used are petrol, diesel and hybrid cars (electric vehicles are 7.1% of the whole fleet but mostly new: 19.5% of the under-3 group). |

**Can coverage be widened correctly?** Tested, with the result below; none is recommended now.
* **New cars (the only large gap, 25%).** A separate model for the *first* inspection would have only make and fuel as inputs, because age is the same for every vehicle at that test. I measured whether that is predictable (grouped cross-validation, UK first MOT at age 3, Dutch first APK at age 4): **ROC-AUC 0.63 / 0.63 / 0.49 for brakes / electrical / engine-related in the UK and 0.53 / 0.55 / 0.46 in the Netherlands**, with defect rates of 0.3% to 8%. That is close to chance: it would add a level that looks informative and is not. **The honest answer for these vehicles is "not covered".** (`ml/first_test_feasibility.json`)
* **Electric vehicles aged 3 to 20.** Technically possible later with an electric-only model on the Dutch data (many electric inspections exist), but it would add only about 1.8 points of coverage today (to 72.4%) and needs new training and validation. Not worth it now.
* **Older than 20 years.** Extrapolating would give numbers without evidence, for 2% of vehicles.
* What was **not** done, deliberately: pretending an age (for example mapping a 1-year-old car to age 3) or reusing the electric vehicles with the petrol curve. That would be inventing data.

**Behaviour of the dashboard for a vehicle that is not covered** (checked in the browser at both sizes): the risk panel says "No estimate for this vehicle" with the reason in plain language (for example "the vehicle is under 3 years old at its last inspection: its first annual inspection has not taken place yet, and the model learns from vehicles that already had one"), shows no bar, no level and no explanation of bars that do not exist, and states that the estimated mileage, the recommended maintenance and the official recalls below still apply (they do). The API returns `covered: false`, the reasons, no systems and no scale. Records entered for such a vehicle are stored but not used by the model (this was a defect: see section 5).

## 2. Visual verification of the dashboard

**How:** the built-in browser pane of this environment could not draw (its window is minimised: screenshots time out). I therefore drove a **real Chrome (version 157) in headless mode through the DevTools protocol** (`scripts/visual_check.py`), against the running stack, at **desktop 1280 x 900** and **phone 390 x 844 with mobile emulation**, in light mode and once in dark mode. It performs the searches, clicks and typing a user would, makes **101 assertions on what is on the page**, measures horizontal overflow and the geometry of the bars, and saves **23 screenshots** to `docs/screenshots/`.

**Scenarios (all at both sizes):** empty state; covered vehicle without records; covered vehicle with maintenance records and an inspection result (measured odometer, history variant); chat with a symptom; electric vehicle (not covered); new petrol car (not covered); vehicle with an open recall; the SRS anomaly vehicle (60,000 km, no brake service); unknown plate; invalid plate; the details section expanded.

**What I looked at myself in the screenshots** (not only the assertions): the risk panel at desktop and phone width (levels, bars, text, expanded details with the reference-rate table); the full desktop page (vehicle card, mileage with range, risk, odometer box, maintenance, recalls, history and forms); the not-covered panels (electric, at both sizes); the maintenance panel; the recall panel; the chat at phone width and desktop; the dark-mode page.

**Confirmed:** bars, levels and texts render correctly; estimated mileage is labelled as an estimate with its range (and as "measured" when a value exists); maintenance, recalls and chat work; nothing overflows horizontally at 390 px; no forbidden wording ("times the average", "probability of failure", "chance of failure", "will fail") appears on any screen; for a not covered vehicle no bar is drawn.

**Problems found by looking, fixed, and checked again:** (1) the engine-related title wrapped to two lines and pushed its bar lower than the other two (titles now have a short heading and a caption, and a check compares the bar heights); (2) for not covered vehicles the explanation of the bars was still shown; (3) a sentence in the maintenance panel began with a lower-case letter; (4) the development badge of the Next.js server appeared on the screen (removed); (5) my first "recall" screenshot actually showed the maintenance panel (wrong selector), which proved that only the assertion had covered the recalls, so I corrected it and looked at the recall panel itself (category, type, date, number, official Hebrew text right-to-left, "Open recall" label).

**Not verified (cannot be, here):** physical phones and other browsers (Safari, Firefox); screen readers and keyboard-only use beyond semantic labels; print layout; slow networks; the 7,877 px full-page phone screenshot was reviewed through its section crops, not as one image. Layouts could differ slightly in other browsers.

## 3. Model 1: is the estimate coherent, and what does the ML add over the CBS?

**Coherence on Israeli vehicles** (random registry sample; no individual odometer exists in open data, so this compares estimates with each other and with official means). Model 1 against three estimates built only from CBS tables (B1: years 1 to A at the official rate of each age band; B2 multiplies by the official ownership mean; B3 also by the official propulsion mean), on about 17,500 vehicles aged 1 to 40:

| CBS-only estimate | Median difference | Within 10% | Differ by more than 25% | Rank correlation |
|---|---|---|---|---|
| By age band | 7.2% | 67% | 17% | 0.97 |
| + ownership | **2.8%** | **84%** | 7% | 0.98 |
| + ownership and propulsion | 10.2% | 47% | 1% | 0.99 |

Model 1 reproduces the official age-by-ownership estimate within a few percent (as designed: it is calibrated to those aggregates). Its annual kilometres are 16.1 thousand (private), 31.4 (leasing), 28.1 (company), 29.8 (rental), 23.8 (diesel), 24.4 (hybrid); the 1st to 99th percentile of the implied annual distance is 12.9 to 33.9 thousand km. Plausibility: **0.06% of vehicles get more than 400,000 km and 0.19% more than 40,000 km a year** (the maximum is 519,000 km), all in diesel/hybrid leasing or company cars; the implausible grid cells (for example a 12-year-old leasing hybrid) practically do not exist in the fleet (0% of leasing cars and 0.5% of rental cars are 8 years or older), so no change is needed, but the limitation (stacked effects are extrapolations) stays documented.

**Is the range understandable?** It is wide because individual vehicles vary a lot (its width is 104% to 116% of the estimate for ages 4 to 19 and 157% for ages 0 to 3; for example 166,200 km with a range of 76,100 to 268,400 for an 11-year-old car), and the dashboard now explains it in plain words: "in the training data about 8 in 10 similar vehicles fall inside such a range, so the true value of this vehicle can easily lie anywhere in it".

**What the learned model adds, measured where individual ground truth exists** (leave-one-market-out: train on two used-car markets, calibrate with the *aggregates* of the third, test on individual vehicles of the third; the lookups use exactly the same aggregates):

| RMSE (km) | UK | India | US |
|---|---|---|---|
| ML without calibration | 38,948 | 74,632 | 129,301 |
| **ML calibrated with age-band aggregates (what Model 1 does)** | **24,983** | **32,071** | **75,777** |
| Lookup of age-band means (analogue of the CBS table by age) | 25,173 | 31,325 | 74,192 |
| Lookup of age-band x fuel means (needs a joint table that the CBS does not publish) | 24,188 | 29,024 | 73,884 |
| Oracle: ML trained on the target market's own vehicles | 21,037 | 28,526 | 72,989 |

**Honest conclusion:** the learned model on its own is far off (R2 negative): **the official aggregates do the work**. Once calibrated, **the ML performs like a lookup of the official table by age**: 0.8% better in the UK, 2.4% and 2.1% worse in India and the US, and worse than a lookup that also has the fuel split (a table that exists for these markets but not for Israel). The interval is not better either: coverage 90%, 80% and 83% against 80% nominal, and 11% to 26% wider than a lookup's. (The lookup interval used the target market's own vehicles, which do not exist for Israel, so it is not an available alternative.) **Real benefit of Model 1 in the delivered system:** a smooth age curve instead of seven coarse bands, a fuel effect, a range, the two-stage architecture the specification requires, and no claim of individual accuracy. It does **not** add measurable accuracy over the CBS lookup, and nobody should present it as doing so. This is inherent to the data (no individual Israeli odometers); it needs no correction, only honesty. (`ml/model1_vs_cbs_results.json`, `ml/model1_plausibility.json`)

## 4. Final flow tests

| Check | Result |
|---|---|
| Automatic tests (pytest, real PostgreSQL and Redis) | **84 passed** (66 before this round + 18 new in `test_flows_matrix.py`) |
| Matrix: 5 vehicles (1 covered, 4 not covered for different reasons: electric and new, new petrol, older than 20, gas) x without records and with maintenance and inspection records | every section present and honest; estimate labelled as an estimate; no overdue claim on an estimated odometer; with records the mileage is shown as measured and the rules change, coverage does not; no model-use claim for a vehicle without a model |
| Chat without an OpenAI key (5 vehicles) | deterministic answer, says so, never invents a risk for a not covered vehicle |
| Chat with a key (mocked transport; covered and not covered) | only pipeline facts reach the model; the user's text never enters the system prompt; the not covered vehicle is described as "NOT AVAILABLE"; a failure falls back deterministically |
| Visual and functional check in Chrome, desktop and phone | **101 / 101** |
| Front end type check and production build | pass |
| 88 real plates end to end (live registry) | see `docs/E2E_REPORT.md` (run after this round's corrections) |
| Information presented as fact | Only registry data and official recalls are shown as facts. The mileage is labelled "Estimated" or "Measured"; risk is a "relative level, not a probability"; rules are "generic intervals, not specific to this make and model"; demonstration records are labelled "[DEMO]". The API and the pages contain no per-vehicle probability, no "times the average" and no exact percentile. |

## 5. Defects and problems found in this round (all corrected)

1. **A vehicle not covered by Model 2 was reported as "the last inspection result is used by the risk model"** when an inspection record existed (found by the matrix test). Now it is used only when the model produces an estimate.
2. Coverage reasons were technical ("age 0 outside the covered range 3-20"). Now plain language, with the real cause (first annual inspection not yet taken).
3. The not covered panel still explained bars that were not drawn.
4. The three risk cards were misaligned because one title wrapped.
5. Chat fallback wording: "is no record overdue" (now readable) and a lower-case sentence start in maintenance.
6. My earlier numbers for coverage and for the share of Israeli vehicles per level (65.6%, 12,597 vehicles) treated vehicles without a first-registration date as not covered, although the system falls back to the manufacture year. Corrected: **70.6% covered**; levels of the covered fleet 30/28/42% (brakes), 34/28/39% (electrical), 42/26/32% (engine-related). The documents were updated.

## 6. Limitations that cannot be removed with the available data

* **No Israeli inspection outcomes and no individual odometers in open data:** Model 2 is validated only on UK (training) and Dutch (independent) data, and Model 1's individual accuracy in Israel is unknown. The levels are relative to UK reference vehicles; their proportions in the Israeli fleet differ (more vehicles in High: 42% for brakes against 31% in the reference).
* **The target is a defect found at the next annual inspection, not a breakdown;** discrimination is modest (ROC-AUC about 0.64 to 0.77), so a level is a coarse screening.
* **29.4% of the fleet gets no risk estimate** (new, very old, electric or gas vehicles); for new cars the data themselves do not support one.
* **Model 1 is, in accuracy, equivalent to a lookup of the official table** (section 3); its range is wide and its calibration relies on stationarity of usage across cohorts. Electric vehicles are treated like petrol.
* **OpenAI chat:** not exercised live in this environment.
* The demo records are generated and labelled; the registry data and recalls are live and public.

## 7. What still needs attention before the demonstration (none blocking)

* Set `OPENAI_API_KEY` in `.env` and try the chat once, if the live language model is to be shown (the deterministic fallback is already verified).
* Run `docker compose up --build` and the seed script on the demonstration machine; the plates for the script are in `docs/DEMO.md`.
* Open the dashboard once in the browser to be used for the presentation (this report could only check headless Chrome).
