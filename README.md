# CSLB License Checker API

API service for querying California Contractors State License Board (CSLB) license data. Returns structured JSON with business info, license status, classifications, bond details, and workers' compensation data.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  Kubernetes Cluster                                  │
│                                                      │
│  ┌─────────────────┐    ┌──────────────────────┐     │
│  │  API Deployment  │    │  CronJob (daily)     │     │
│  │  FastAPI + SQLite│◄───│  Download CSV →      │     │
│  │                  │    │  Rebuild SQLite DB   │     │
│  └────────┬─────────┘    └──────────┬───────────┘     │
│           └────────┬────────────────┘                 │
│                    ▼                                  │
│           ┌────────────────┐                          │
│           │  PVC (data/)   │                          │
│           │  licenses.db   │                          │
│           └────────────────┘                          │
└──────────────────────────────────────────────────────┘
```

**Two data sources (configurable):**

- **CSV/SQLite** (default) — CSLB's bulk CSV (~240k records) loaded into SQLite for fast lookups
- **Firecrawl** (optional) — Live scraping of the CSLB website using browser automation for real-time data

## Tech Stack

- **Python 3.11+** / **FastAPI** / **Uvicorn** — async API server
- **SQLite** via `aiosqlite` — lightweight database, no external dependencies
- **pandas** — CSV parsing and data import
- **Firecrawl** (`firecrawl-py`) — AI-powered web scraping with browser actions
- **Docker** — containerization
- **Helm 3** — Kubernetes deployment, configurable for any cluster
- **Kubernetes CronJob** — daily CSV refresh from CSLB data portal

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/license/{number}` | Single license lookup |
| `POST` | `/api/licenses` | Bulk lookup (up to 100) |
| `GET` | `/api/stats` | Database stats |
| `GET` | `/health` | Health check |

Add `?source=firecrawl` to any GET request to use live scraping instead of CSV data.

## Quick Start

```bash
# Install dependencies
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Load CSV data
python -m app.csv_loader /path/to/MasterLicenseData.csv

# Start API
uvicorn app.main:app --reload

# Test
curl http://localhost:8000/api/license/1041069
```

## Docker

```bash
docker-compose up --build
```

## Kubernetes (Helm)

```bash
# Build image (available to Docker Desktop K8s automatically)
docker build -t cslb-license-api:latest .

# Deploy
helm install cslb-api ./helm/cslb-license-api

# Access
kubectl port-forward svc/cslb-api-cslb-license-api 8000:8000
```

### Helm Configuration

Key values in `helm/cslb-license-api/values.yaml`:

| Value | Default | Description |
|-------|---------|-------------|
| `config.dataSource` | `csv` | `csv` or `firecrawl` |
| `secrets.firecrawlApiKey` | `""` | Firecrawl API key |
| `csvRefresh.enabled` | `true` | Enable daily CSV refresh CronJob |
| `csvRefresh.schedule` | `0 6 * * *` | Cron schedule (daily 6 AM UTC) |
| `persistence.size` | `1Gi` | PVC storage size |
| `ingress.enabled` | `false` | Enable Ingress |

## Configuration

Copy `.env.example` to `.env` and set:

```
DATA_SOURCE=csv              # csv or firecrawl
DATABASE_PATH=data/licenses.db
FIRECRAWL_API_KEY=           # Required for firecrawl source
```

## Project Structure

```
├── app/
│   ├── main.py              # FastAPI routes
│   ├── config.py            # Environment settings
│   ├── database.py          # SQLite queries
│   ├── models.py            # Pydantic models
│   ├── csv_loader.py        # CSV → SQLite import
│   ├── classifications.py   # CSLB code descriptions
│   └── firecrawl_client.py  # Live scraping client
├── scripts/
│   └── refresh_csv.sh       # Daily CSV download script
├── helm/
│   └── cslb-license-api/    # Helm chart
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```
