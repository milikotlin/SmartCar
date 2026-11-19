# Test report

Environment: Docker Compose stack (backend Python 3.13 with the exact library versions used for training, PostgreSQL 15, Redis 7, Next.js 15), Windows host, run on 2026-11-18/19.

## 1. Automatic tests (pytest inside the backend container, real PostgreSQL and Redis)

Command: `docker compose exec -T backend python -m pytest -q`  ->  **115 passed** (61 at the first delivery, 66 after the risk-scale change, 84 after the final flow matrix, 111 after the final technical review: security, independence of the two models, colour and manufacturer translation; see FINAL_TECHNICAL_REVIEW.md).

| File | Tests | What is checked |
|---|---|---|
| `test_flows_matrix.py` | 18 | **Final flow matrix** on real registry rows: one covered vehicle and four not covered for different reasons (electric and new, new petrol, older than 20 years, gas), each without records and with maintenance and inspection records; the chat without an OpenAI key for all five, with a key (mocked transport) for a covered and a not covered vehicle, and when the language model fails. Found the defect "history used by the model" for a vehicle without a model |
| `test_translation_features.py` | 18 | Every one of 15 **real registry rows** (covering makes, fuels, ownerships, ages) is translated with no Hebrew left in the make; all fuel values and manufacturer prefixes found in a 20,000-row registry sample; unknown values are returned as published, never guessed; "1600 CC" style parsing never raises; make vocabulary of the training data (BMW -> Bmw, Opel/Vauxhall); age of the last inspection; **registry dates (licence valid until) do not change the risk indicator** |
| `test_models.py` | 23 | **Model 1:** reproduces the reference points of the offline training; monotone in age for every fuel; range brackets the estimate; ownership pattern of the official statistics (leasing and company far above private); population level within 5% of CBS in every age band; notes for electric, capped and extrapolated ages. **Model 2:** artifacts complete (boosters, card, reference scale); the Model-1 estimate is not a feature; outputs valid and levels consistent with the reference percentile; **one common scale: percentile and level are monotone in the model output across all ages, fuels and makes, and all three levels occur**; **Hyundai i20 age 4 against Nissan Micra age 12: the Micra has the higher probability, percentile and level in every system**; the complementary same-age position compresses the age difference; variant selection (cold / odometer / history / both); a previous defect raises the risk of that system; risk grows with age; declines electric, gas and ages outside 3-20 with a reason; unknown make grouped, not rejected; **golden predictions and levels** (125 cases computed in the training environment equal those computed in the API image to 1e-5); **levels grounded in data: observed defect rate Low < Moderate < High for every variant, system and country (UK cross-fitted and independent Dutch), Low and High statistically separated, each UK level at least 19% of vehicles; standardising the interval to 12 months changes AUC by no more than 0.01 (actual maximum 0.002)**; the card records the foreign validation and the absence of Israeli validation; **two-stage inference latency below 500 ms** (measured median about 30-35 ms, maximum about 110-135 ms) |
| `test_rules_chat.py` | 11 | Record classification (category, then English and Hebrew keywords); status from time and **measured** kilometres (ok, due soon, overdue); no oil rule for electric vehicles; **the SRS anomaly vehicle (60,000 km, no brake record) trips the brake rule**; an estimated odometer never proves an overdue service; the system prompt carries only pipeline facts and the guardrails; user text never enters the system prompt; deterministic fallback; OpenAI request payload and answer (mocked HTTP transport); OpenAI failure falls back instead of breaking |
| `test_api.py` | 14 | Health; translated profile; invalid plates rejected (422) on both endpoints; unknown plate 404; prediction without records (cold variant, estimate labelled as estimate, three statements kept apart, recalls shown; **each system has a level, a rank rounded to 5 and a same-age label, and the response contains no probability, no "times the average" and no percentile number**); measured odometer replaces the estimate and selects the odometer variant; electric vehicle not covered but other sections present; **history used only when the recorded inspection is the last registry test**; duplicate inspection 409; maintenance records drive the rules **and are not treated as inspection history**; chat endpoint and input validation; **registry outage answered as 503 instead of a crash** |

The government HTTP services are replaced in `test_api.py` by recorded real registry rows and a recall row (so that the test is reproducible); the live services are exercised in section 3.

## 2. Front end

* `npx tsc --noEmit` and the production build: no type errors (after the round-5 change as well).
* `npm run build` (Next.js 15 production build, includes type and lint checks): compiled successfully; one static route.
* Interactive check in the browser pane against the running stack: search of real plates, rendering of mileage, the three risk bars, maintenance rules, recalls, history and forms; chat dialog answering from the deterministic fallback. After the round-5 change: for the Hyundai i20 2022 the bar geometry was measured (segments 36% / 33% / 31% of the width, marker at 20 / 10 / 5 inside the Low segment, the three level pills, the reference-rates table in the details); for the Nissan Micra 2014 at phone width (375 px) the three cards render without horizontal overflow. (The browser window was minimised during the runs, so the checks read the rendered page and its geometry; screenshots were not possible.)

## 2b. Visual and functional check in a real browser (final round)

`scripts/visual_check.py` drives headless **Chrome 157** through the DevTools protocol against the running stack at desktop (1280 x 900) and phone (390 x 844, mobile emulation) size, light and dark: 10 scenarios (empty, covered without records, covered with records and history, the refusal of the records form without the workshop key, chat, electric not covered, new car not covered, open recall, anomaly vehicle, unknown plate, invalid plate), **133 assertions**, horizontal-overflow and bar-geometry measurements, and 23 screenshots in `docs/screenshots/` that were looked at, not only asserted. Details, what was fixed after looking and what could not be verified: [FINAL_REPORT.md](FINAL_REPORT.md) section 2.

## 3. End-to-end with real Israeli plates (`scripts/e2e_live.py`)

88 real plates (random sample of the public registry, stratified by fuel and age; none used for training or seeding) against the live data.gov.il registry and recall services: see [E2E_REPORT.md](E2E_REPORT.md). Every plate is checked for translation, plausibility of the mileage range, labelling of the estimate, validity of the risk block (or a stated reason for declining), consistency of the recall block, completeness of the maintenance block and the rule that an estimated odometer never proves an overdue service; plus invalid and unknown plates, the cache and the chat endpoint.

## 4. Data and model verification

* UK extraction: CRC32 and size of every full decompressed stream equal the values in the zip headers (2022 and 2023, results and items); structure, sampling rule, referential integrity, monthly completeness and stability of the item coverage checked: [UK_EXTRACTION.md](UK_EXTRACTION.md). The root cause of the earlier corruption (wrong decoder for the item files) is documented there.
* Model quality, validation by time and by unseen vehicles, independent Dutch validation, Logistic Regression benchmark, calibration: [MODEL_CARDS.md](MODEL_CARDS.md).
* Notebooks 01-09 contain the research experiments, with their own checks (leakage audits, paired bootstrap intervals, three random splits).

## 5. Seeded demonstration

`scripts/seed_demo.py` created 21 real plates with generated, "[DEMO]"-labelled records through the public API (this also exercises the write endpoints): 6 vehicles have an inspection result matching the registry's last test (history variant), one is the anomaly vehicle.

## 6. Not tested / known gaps

* The **live OpenAI call** was not exercised (no API key in this environment). It is covered by tests with a mocked transport (payload, headers, answer parsing, failure fallback). With a key, the first call should be checked manually.
* **Israeli accuracy** of the models cannot be tested: there are no Israeli inspection outcomes or per-vehicle odometers in open data.
* No load or concurrency test beyond sequential requests; no cross-browser test (only the Chromium-based pane); no accessibility audit beyond semantic labels.
* The front end has no automated component tests (type check, production build and interactive check only).
