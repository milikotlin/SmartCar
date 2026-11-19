# SmartCar-Ops

Plataforma de manutenção preditiva e gestão de veículos. A partir de uma placa israelense, cruza dados em tempo real do Ministério dos
Transportes (data.gov.il) com dois modelos de Machine Learning (XGBoost), regras de manutenção, recalls oficiais e um chat de diagnóstico
(OpenAI gpt-4o-mini com Context Injection).

O sistema **separa três tipos de informação**, na API, na interface e no chat:

| Tipo | O que é | Origem |
|---|---|---|
| **Risco relativo de defeito em inspeção** | Nível **Baixo / Moderado / Alto** (por sistema: freios, elétrico, motor) em comparação com todos os veículos de referência do UK, de qualquer idade, para a *próxima inspeção anual*; mais uma comparação complementar com veículos da mesma idade. Não é probabilidade | Model 2 (XGBoost) treinado com inspeções reais do UK (MOT) e validado com a Holanda (RDW) |
| **Manutenção recomendada** | Intervalos genéricos de serviço aplicados aos registros do próprio veículo | Regras (não é ML) |
| **Recall oficial** | Fato publicado pela autoridade | Dados abertos do Ministério dos Transportes |

**Não é previsão de pane** e **não é uma probabilidade validada para Israel** (não existem resultados de inspeção israelenses em dados abertos).
Veja `docs/LIMITATIONS.md`.

Documentação: `docs/SRS_v2.md` (SRS atualizado **com o registro das alterações em relação à especificação original**), `docs/MODEL_CARDS.md`,
`docs/RISK_SCALE.md` (escala de risco, antes e depois), `docs/TEST_REPORT.md`, `docs/E2E_REPORT.md`, `docs/UK_EXTRACTION.md`, `docs/DEMO.md`, `docs/LIMITATIONS.md`. Especificação original:
`SmartCar-Ops_SRS.pdf` e `SmartCar-Ops_מסמך_אפיון.pdf`.

## Rodando

Pré-requisito: Docker Desktop.

```bash
cp .env.example .env          # opcional: preencha OPENAI_API_KEY para ativar o chat com o modelo de linguagem
docker compose up --build
docker compose exec backend alembic upgrade head
python scripts/seed_demo.py   # opcional: 21 placas reais + registros de demonstração rotulados "[DEMO]"
```

- Frontend: `http://localhost:3000` · API: `http://localhost:8000` (docs interativas em `/docs`)
- Sem `OPENAI_API_KEY` o chat responde por um modelo determinístico baseado nos mesmos fatos (e diz isso).

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/predict/4908732
curl "http://localhost:8000/api/v1/predict/4908732?odometer_km=123456"
```

## Testes

```bash
docker compose run --rm backend python -m pytest -q          # unitários, modelos, API (com PostgreSQL e Redis reais)
python scripts/e2e_live.py                                    # ~90 placas israelenses reais contra a stack em execução -> docs/E2E_REPORT.md
docker compose run --rm --no-deps frontend npx tsc --noEmit   # tipos do frontend
```

## Estrutura

```
backend/app/
  main.py                    FastAPI; carrega os modelos uma vez no startup
  ml/mileage.py              Model 1: quilometragem estimada (XGBoost + calibração CBS) com intervalo
  ml/risk.py                 Model 2: risco de defeito na próxima inspeção (4 variantes XGBoost por sistema)
  ml/artifacts/              modelos exportados (XGBoost JSON) + model cards
  services/                  gov_api, translation, features, prediction (orquestração), maintenance_rules, recalls, chat
  api/v1/                    vehicles, predict, records (manutenção/inspeções), chat
  models/, alembic/          PostgreSQL 15 em 3NF: vehicles, maintenance_records, inspection_records
backend/tests/               pytest
frontend/                    Next.js 15 + Tailwind v4 (painel de risco, manutenção, recalls, histórico, chat)
ml/src, ml/notebooks/        pesquisa e treino offline (notebooks 01-09), final_model1.py, final_model2.py
scripts/                     seed_demo.py, e2e_live.py, build_model_cards.py, make_golden.py
docs/                        SRS_v2, model cards, relatórios de teste, extração do UK, limitações, demo
```

## Retreinar os modelos (offline)

```bash
ml/.venv/Scripts/python.exe -I -X utf8 ml/src/final_model1.py      # Model 1 (Datasets 7+8+3 + calibração CBS)
ml/.venv/Scripts/python.exe -I -X utf8 ml/src/mot_vehicle_sample.py 2022 41   # extração do UK, verificada por CRC32 (idem 2023)
ml/.venv/Scripts/python.exe -I -X utf8 ml/src/verify_uk_extraction.py
ml/.venv/Scripts/python.exe -I -X utf8 ml/src/final_model2.py      # Model 2
ml/.venv/Scripts/python.exe -I -X utf8 scripts/make_golden.py && python scripts/build_model_cards.py
```
Os dados brutos ficam fora do projeto (`~/smartcar_data`, variável `SMARTCAR_DATA_DIR`).
