# AusTwin Urban Climate Copilot

Monorepo for the **AusTwin** digital twin portal, **CityForesight** heat forecasting, and **UrbanSense** anomaly detection with an RDFLib urban climate ontology.

## Structure

```
austwin-website/
├── apps/web/                 # React + Vite frontend
├── services/cityforesight/   # FastAPI + PyTorch forecasting API (:8000)
├── services/urbansense/      # FastAPI anomaly detection + ontology (:8001)
├── data/processed/           # ASOS CSV, tract GeoJSON, morphology table (generated)
├── data/ontology/            # austwin.ttl + austwin.jsonld (generated)
└── docker-compose.yml        # Local web + CityForesight + UrbanSense
```

## Quick start

### Prerequisites

- Node.js 20+
- [Conda](https://docs.conda.io/en/latest/miniconda.html) (Miniconda or Anaconda)

### Install (one-time)

```bash
npm run setup          # creates conda env `austwin` + npm install
conda activate austwin
```

This replaces the old per-service `.venv` folders with a single conda environment at the repo root (`environment.yml`).

### Fetch data & train models (first run)

With `austwin` activated (or via `scripts/run-conda.sh` automatically):
npm run data:fetch      # ASOS KAUS 2018–2024 + real Travis County census tracts
npm run train:baseline  # Plain LSTM (station heat index)
npm run train:kil       # KIL LSTM (tract-level with morphology)
npm run eval            # Phase gate: KIL ≥15% RMSE improvement
```

**Data sources (real):**

| Dataset | Source |
|---------|--------|
| Weather (KAUS) | Iowa Environmental Mesonet ASOS API |
| Tract boundaries | U.S. Census TIGER/Line (Travis County, ~290 tracts) |
| Impervious / canopy / drainage | NLCD 2021 land cover (USGS MRLC), zonal stats per tract |
| Population density | Census ACS 2022 5-year (`CENSUS_API_KEY`) or area-weighted fallback |

Optional flags:

```bash
# Free Census API key: https://api.census.gov/data/key_signup.html
cp .env.example .env   # then paste your key into .env once
npm run data:fetch
```

### Development

```bash
conda activate austwin
npm start              # Web :5173 + CityForesight :8000 + UrbanSense :8001
# alias: npm run dev
# or separately:
npm run dev:web
npm run dev:api
npm run dev:sense
```

`npm start` works with the conda env **activated**, or it will use `conda run -n austwin` if the env exists but is not active.

**Port conflict?** If CityForesight fails to load, another app (often **Cursor**) may be using port 8000. Set in `.env`:

```
CITYFORESIGHT_DEV_PORT=8010
URBANSENSE_DEV_PORT=8011
URBANSENSE_CITYFORESIGHT_URL=http://localhost:8010
```

Then restart `npm start`.

Open [http://localhost:5173/one-pager](http://localhost:5173/one-pager) — **Data** → **UrbanSense**, or **Tools** → **CityForesight**.

### UrbanSense setup (Phase 2)

```bash
npm run ontology:build  # Seed tract + morphology triples → data/ontology/
npm run eval:sense      # Synthetic hotspot gate (≥80% alert/extreme)
```

### Docker

```bash
docker-compose up
```

## API

### CityForesight (`:8000`)

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Service status |
| `GET /forecasts/current` | GeoJSON choropleth + 1–6 hr heat index per tract |
| `GET /forecasts/tract/:geoid` | Single-tract forecast series |
| `GET /forecasts/search?q=` | Geocode address → tract forecast (or candidate list) |
| `GET /forecasts/lookup?lat=&lon=` | Point-in-tract forecast lookup |
| `GET /metrics/benchmark` | Baseline vs KIL RMSE benchmark |
| `POST /admin/refresh` | Force inference refresh (`X-Admin-Token` header) |

Local dev proxies `/api/*` → `http://localhost:8000`.

### UrbanSense (`:8001`)

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Service status + CityForesight reachability |
| `GET /anomalies/current` | GeoJSON choropleth with anomaly scores |
| `GET /anomalies/tract/:geoid` | Tract detail + ontology subgraph |
| `GET /ontology/tract/:geoid` | JSON-LD subgraph for tract |
| `GET /ontology/export.ttl` | Full Turtle ontology dump |
| `POST /admin/refresh` | Force anomaly recompute (`X-Admin-Token` header) |

Local dev proxies `/api/sense/*` → `http://localhost:8001`.

## Frontend routes

| Path | Page |
|------|------|
| `/` | Redirects to one-pager |
| `/one-pager` | AusTwin interactive landing |
| `/cityforesight` | Live forecast choropleth dashboard with address search |
| `/urbansense` | Heat anomaly choropleth + tract ontology detail |
| `/coolpath` | External CoolPath app |
| `/thermalscape` | External Thermalscape VR |

## Deployment

### Frontend (Vercel)

- Root `vercel.json` builds `apps/web`
- Set `VITE_API_URL` to your API origin, or use the `/api` rewrite to your hosted CityForesight service

### API (Railway / Render / Fly.io)

```bash
cd services/cityforesight
docker build -t cityforesight .
# Deploy with artifacts volume containing trained weights (kil_lstm.pt, benchmark.json)
```

Environment variables:

- `CITYFORESIGHT_DATA_DIR` — path to `data/` (optional)
- `CITYFORESIGHT_ARTIFACTS_DIR` — path to model weights
- `CITYFORESIGHT_ADMIN_TOKEN` — admin refresh token (production)
- `URBANSENSE_CITYFORESIGHT_URL` — CityForesight base URL (default `http://localhost:8000`)
- `URBANSENSE_ADMIN_TOKEN` — UrbanSense admin refresh token

### Scheduled inference

Configure a cron (every 15 min) to `POST /admin/refresh` or rely on the built-in APScheduler in the API process.

## Phase scope

**Phase 1 (delivered):** CityForesight — LSTM + KIL land-cover features, tract choropleth UI, benchmark evaluation.

**Phase 2 (delivered):** UrbanSense — spatial/temporal/morphology anomaly scoring, RDFLib ontology (Turtle + JSON-LD), `/urbansense` dashboard, OnePager Data node integration.

**Deferred (Phase 2b–4):** Neo4j knowledge graph, ERCOT load, MODIS LST, CityGML ingestion, CityGuide, CityCommand, C3AN evaluation.

## License

UT City CoLab × TExUS Lab — AusTwin framework.
