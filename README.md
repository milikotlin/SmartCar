# SmartCar-Ops

Plataforma de manutenção preditiva e gestão inteligente de veículos. Cruza dados históricos
offline (Kaggle) com dados em tempo real do Ministério dos Transportes de Israel (data.gov.il)
através de um pipeline de Machine Learning de dois estágios (Regressão + XGBoost) e oferece
diagnóstico em linguagem natural via GenAI (OpenAI, com Context Injection).

Especificação completa em `SmartCar-Ops_מסמך_אפיון.pdf` e `SmartCar-Ops_SRS.pdf`.

## Status atual

**Sprint 1 — Backend & Data Ingestion**
- [x] Docker Compose (Postgres 15, Redis 7, backend FastAPI)
- [x] Schema do banco (3NF: `vehicles` + `maintenance_records`) via Alembic
- [x] Integração assíncrona com a API do Gov (CKAN / data.gov.il), com tradução Hebraico → Inglês
- [x] Cache no Redis com TTL de 24h

**Sprint 2 — Frontend (React/Next.js)**
- [x] Dashboard em Next.js 15 + Tailwind v4 (App Router, TypeScript)
- [x] Zona A (busca de placa), Zona B (ficha do veículo + risco + histórico), Zona C (chat, placeholder)
- [x] Consumo real do `GET /api/v1/vehicles/{placa}` do backend
- [x] Tema claro/escuro automático (`prefers-color-scheme`), responsivo (mobile → desktop)

- [ ] Sprint 3 — Pipeline de ML (Regressão + XGBoost)
- [ ] Sprint 4 — GenAI (OpenAI Context Injection) + fallback determinístico

## Rodando localmente

Pré-requisito: Docker Desktop instalado.

```bash
docker compose up --build
```

Em outro terminal, aplique as migrations do banco:

```bash
docker compose exec backend alembic upgrade head
```

Testar o backend:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/vehicles/29565310
```

(troque `29565310` por uma placa real de 7 ou 8 dígitos cadastrada em Israel — o dataset público
tem ~4,1 milhões de registros).

- API: `http://localhost:8000` (docs interativas em `/docs`)
- Frontend: `http://localhost:3000`

## Estrutura

```
backend/
  app/
    main.py            # FastAPI app + rotas
    config.py           # variáveis de ambiente (pydantic-settings)
    database.py          # engine/session async do SQLAlchemy
    redis_client.py      # cache Redis (24h TTL)
    models/               # ORM: Vehicle, MaintenanceRecord
    schemas/               # Pydantic: VehicleProfile
    services/
      gov_api.py            # client httpx para o CKAN (data.gov.il)
      translation.py          # tradução Hebraico -> Inglês dos campos do Gov
    api/v1/
      vehicles.py              # GET /api/v1/vehicles/{license_plate}
  alembic/                       # migrations do schema

frontend/
  app/
    layout.tsx        # fontes (IBM Plex Sans/Mono via next/font), metadata
    page.tsx            # orquestra o estado da busca (idle/loading/error/success)
    globals.css           # design tokens Tailwind v4 (@theme), claro/escuro
  components/
    Header.tsx, SearchBar.tsx           # Zona A
    VehicleSpecCard.tsx                   # Zona B — ficha do veículo (dados reais)
    RiskPanel.tsx, RiskGauge.tsx            # Zona B — risco (estado "pending" até o Sprint 3)
    MaintenanceHistory.tsx                    # Zona B — histórico (estado vazio até o Sprint 3)
    DiagnosticChatFab.tsx                       # Zona C — botão travado, "arriving Sprint 4"
    ui/Skeleton.tsx, ui/StatusPill.tsx
  lib/
    api.ts       # fetch client para o backend
    types.ts       # tipos TS espelhando o VehicleProfile
```

### Nota de design (Sprint 2)

Os gauges de risco e o histórico de manutenção estão implementados na UI mas mostram um
estado "pending"/vazio honesto, em vez de dado fabricado — o backend ainda não expõe o
pipeline de ML (Sprint 3) nem uma rota de histórico. Isso evita confundir dado real com
mock na hora da defesa: tudo que aparece preenchido no dashboard hoje veio de verdade da
API do governo.

### Endpoint implementado (UC-01: Real-Time Vehicle Profiling)

`GET /api/v1/vehicles/{license_plate}` — recebe uma placa de 7 ou 8 dígitos, verifica o cache Redis,
se ausente consulta a API do Gov (CKAN, resource_id `053cea08-09bc-40ec-8f7a-156f0677aff3`),
traduz os campos em hebraico (fabricante, combustível, propriedade) para inglês e retorna o
perfil do veículo. Note que o dataset do Gov **não** inclui quilometragem nem cilindrada do
motor — por isso o documento prevê a API-Ninjas (specs complementares) e o modelo de Regressão
(Stage 1, imputação de km) nos próximos sprints.
