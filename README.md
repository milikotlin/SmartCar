# SmartCar-Ops

Predictive maintenance and vehicle management platform. From an Israeli license plate, it combines live data from the Ministry of Transport (data.gov.il) with two
machine-learning models (XGBoost), maintenance rules, official recalls and a diagnostic chat (OpenAI gpt-4o-mini with context injection).

The system **keeps three kinds of information separate**, in the API, in the interface and in the chat:

| Kind | What it is | Source |
|---|---|---|
| **Relative risk of a defect at inspection** | A **Low / Moderate / High** level (per system: brakes, electrical, engine-related) compared with all UK reference vehicles of any age, for the *next annual inspection*; plus a complementary comparison with vehicles of the same age. It is not a probability | Model 2 (XGBoost) trained on real UK inspections (MOT) and validated on the Netherlands (RDW) |
| **Recommended maintenance** | Generic service intervals applied to the vehicle's own records | Rules (not ML) |
| **Official recall** | A fact published by the authority | Ministry of Transport open data |

It is **not a breakdown prediction** and **not a probability validated for Israel** (Israeli inspection results are not available as open data). See `docs/LIMITATIONS.md`.

Documentation: `docs/SRS_v2.md` (the updated SRS, **with the change log against the original specification**), `docs/MODEL_CARDS.md`,
`docs/FINAL_TECHNICAL_REVIEW.md` (security, model audits and corrections), `docs/FINAL_REPORT.md` (readiness report), `docs/RISK_SCALE.md` (the risk scale, before and after),
`docs/MODEL2_VS_AGE_BASELINE.md` (what Model 2 adds beyond the age of the vehicle), `docs/TEST_REPORT.md`, `docs/E2E_REPORT.md`, `docs/UK_EXTRACTION.md`, `docs/DEMO.md`, `docs/LIMITATIONS.md`.
Original specification: `SmartCar-Ops_SRS.pdf` and `SmartCar-Ops_מסמך_אפיון.pdf`. Also: `docs/OPENAI_SETUP.md` (configuring and testing the OpenAI chat without exposing the key) and `docs/DEFENCE_LIMITATIONS.md` (the limitations of both models in plain language, for the academic defence).

## Running

Prerequisite: Docker Desktop.

```bash
cp .env.example .env          # set RECORDS_WRITE_KEY (the workshop key; generate one with: python -c "import secrets; print(secrets.token_urlsafe(18))") and, optionally, OPENAI_API_KEY
docker compose up --build
docker compose exec backend alembic upgrade head
python scripts/seed_demo.py   # optional: 21 real plates + demonstration records labelled "[DEMO]"
```

- Frontend: `http://localhost:3000` · API: `http://localhost:8000` (interactive docs at `/docs`). The ports are bound to `127.0.0.1`.
- Writing records (maintenance / inspection result) requires the **workshop key** (`RECORDS_WRITE_KEY` in `.env`, "Workshop key" field in the dashboard; reading is open). With no key configured, writing is disabled.
  `.env` is never committed; to share the project use `python scripts/make_share_zip.py` (tracked files only).
- Without `OPENAI_API_KEY` the chat answers from a deterministic model built from the same facts (and says so). To configure and test the real OpenAI call without exposing the key, see
  `docs/OPENAI_SETUP.md` (`python scripts/check_openai.py --direct`). The presentation script is `docs/DEMO.md`.

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/predict/4908732
curl "http://localhost:8000/api/v1/predict/4908732?odometer_km=123456"
```

## Tests

```bash
docker compose run --rm backend python -m pytest -q          # unit, models, API (with real PostgreSQL and Redis): 115 tests
python scripts/e2e_live.py                                    # ~90 real Israeli plates against the running stack -> docs/E2E_REPORT.md
python scripts/visual_check.py                                # headless Chrome: desktop and phone, 133 checks + screenshots in docs/screenshots/
docker compose run --rm --no-deps frontend npx tsc --noEmit   # frontend types
```

## Structure

```
backend/app/
  main.py                    FastAPI; loads the models once at startup
  security.py                workshop key for writes and rate limits
  ml/mileage.py              Model 1: estimated mileage (XGBoost + CBS calibration) with a range and a reliability flag
  ml/risk.py                 Model 2: risk of a defect at the next inspection (4 XGBoost variants per system)
  ml/artifacts/              exported models (XGBoost JSON) + model cards
  services/                  gov_api, translation, features, prediction (orchestration), maintenance_rules, recalls, chat
  api/v1/                    vehicles, predict, records (maintenance/inspections), chat
  models/, alembic/          PostgreSQL 15 in 3NF: vehicles, maintenance_records, inspection_records
backend/tests/               pytest
frontend/                    Next.js 15 + Tailwind v4 (risk panel, maintenance, recalls, history, chat)
ml/src, ml/notebooks/        offline research and training (notebooks 01-09), final_model1.py, final_model2.py, audits
scripts/                     seed_demo.py, e2e_live.py, visual_check.py, check_openai.py, make_share_zip.py, build_model_cards.py, make_golden.py
docs/                        SRS_v2, model cards, test reports, UK extraction, limitations, demo
```

## Retraining the models (offline)

```bash
ml/.venv/Scripts/python.exe -I -X utf8 ml/src/final_model1.py      # Model 1 (Datasets 7+8+3 + CBS calibration)
ml/.venv/Scripts/python.exe -I -X utf8 ml/src/model1_smooth_calibration.py --apply 3   # curve smoothing and support table (after final_model1.py)
ml/.venv/Scripts/python.exe -I -X utf8 ml/src/mot_vehicle_sample.py 2022 41   # UK extraction, verified by CRC32 (same for 2023)
ml/.venv/Scripts/python.exe -I -X utf8 ml/src/verify_uk_extraction.py
ml/.venv/Scripts/python.exe -I -X utf8 ml/src/final_model2.py      # Model 2
ml/.venv/Scripts/python.exe -I -X utf8 scripts/make_golden.py && python scripts/build_model_cards.py
```

The raw data live outside the project (`~/smartcar_data`, variable `SMARTCAR_DATA_DIR`).
