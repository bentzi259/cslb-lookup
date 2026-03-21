# CSLB Lookup

API service for querying California Contractors State License Board (CSLB) license data. Returns structured JSON with business info, license status, classifications, bond details, workers' compensation, and personnel data.

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
- **Scraper** (free) — Direct HTTP scraping of the CSLB website for real-time data, no API key required

## Tech Stack

- **Python 3.11+** / **FastAPI** / **Uvicorn** — async API server
- **SQLite** via `aiosqlite` — lightweight database, no external dependencies
- **pandas** — CSV parsing and data import
- **httpx** — direct HTTP scraping of CSLB website (free, no API key)
- **Docker** — containerization
- **Helm 3** — Kubernetes deployment, configurable for any cluster
- **Kubernetes CronJob** — daily CSV refresh from CSLB data portal

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check (public) |
| `GET` | `/api/stats` | Database statistics |
| `GET` | `/api/field-metadata` | Distinct values for enum-like fields |
| `GET` | `/api/license/{number}` | Single license lookup |
| `POST` | `/api/licenses` | Bulk lookup (up to 100) |

### Data Source Selection

**1. Default for all requests** — set `DATA_SOURCE` in `.env`:
```
DATA_SOURCE=csv          # local SQLite database (default)
DATA_SOURCE=scraper      # free direct HTTP scraping of CSLB website
```

**2. Per-request override** — append `?source=` to any request:
```bash
curl http://localhost:8000/api/license/1041069?source=csv
curl http://localhost:8000/api/license/1041069?source=scraper
```

For bulk requests, set `"source"` in the JSON body:
```json
{"license_numbers": ["1041069"], "source": "scraper"}
```

**Priority:** per-request param > `DATA_SOURCE` env var > defaults to `csv`

> **Scraper** — free, no API key needed. Fetches the CSLB license detail page directly via HTTP and parses the HTML. Limited to 10 licenses per bulk request.

### Response Schema

Each license lookup returns a `LicenseResponse` object. Some fields are only populated by one data source:

```jsonc
{
  "license_number": "1105295",
  "last_update": "03/18/2026",              // CSV only
  "extract_date": "Data current as of ...", // Scraper only
  "business_information": {
    "business_name": "SKYLINE BUILDERS | SKYLINE ENERGY ROOFING INC",
    "full_business_name": null,             // CSV only
    "address": "13615 VICTORY BLVD #201, VAN NUYS, CA, 91401",
    "county": "Los Angeles",               // CSV only
    "phone": "(669) 377 3687",
    "entity": "Corporation",
    "issue_date": "05/26/2023",
    "reissue_date": null,
    "expire_date": "05/31/2027"
  },
  "license_status": {
    "status": "CLEAR",                     // CSV: code, Scraper: full sentence
    "secondary_status": "Pending IFS",     // CSV only
    "additional_status": null,             // Scraper only (detailed explanation)
    "inactivation_date": null,
    "reactivation_date": null
  },
  "contractors_bond": {
    "bond_number": "7901210858",
    "bond_amount": "25000",                // CSV: raw number, Scraper: "$25,000"
    "bond_company": "NATIONWIDE MUTUAL INSURANCE COMPANY",
    "effective_date": "02/05/2026"
  },
  "classifications": [
    { "code": "B", "description": "General Building Contractor" },
    { "code": "C39", "description": "Roofing Contractor" }
  ],
  "workers_compensation": {
    "coverage_type": "Workers' Compensation Insurance",
    "insurance_company": "STATE COMPENSATION INSURANCE FUND",
    "policy_number": "9337947",
    "effective_date": "04/29/2023",
    "expire_date": "04/29/2027"
  },
  "personnel": null,                       // Scraper only
  "asbestos_reg": null,
  "data_source": "csv"
}
```

**CSV-only fields:** `last_update`, `full_business_name`, `county`, `secondary_status`

**Scraper-only fields:** `extract_date`, `additional_status`, `personnel`

### Usage Examples

```bash
# Health check
curl http://localhost:8000/health

# Single license lookup
curl http://localhost:8000/api/license/1041069

# Bulk lookup
curl -X POST http://localhost:8000/api/licenses \
  -H "Content-Type: application/json" \
  -d '{"license_numbers": ["1041069", "1000002"]}'

# Database stats
curl http://localhost:8000/api/stats

# Field metadata (distinct values for enum-like fields)
curl http://localhost:8000/api/field-metadata

# Swagger docs
open http://localhost:8000/docs
```

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
docker build -t cslb-lookup:latest .

# Deploy
helm install cslb-lookup ./helm/cslb-lookup

# Access
kubectl port-forward svc/cslb-lookup 8000:8000
```

### Helm Configuration

Key values in `helm/cslb-lookup/values.yaml`:

| Value | Default | Description |
|-------|---------|-------------|
| `config.dataSource` | `csv` | `csv` or `scraper` |
| `secrets.apiKey` | `""` | API key for authentication |
| `csvRefresh.enabled` | `true` | Enable daily CSV refresh CronJob |
| `csvRefresh.schedule` | `0 6 * * *` | Cron schedule (daily 6 AM UTC) |
| `persistence.size` | `1Gi` | PVC storage size |
| `ingress.enabled` | `false` | Enable Ingress |

## Configuration

Copy `.env.example` to `.env` and set:

```
API_KEY=                     # API key for auth (empty = auth disabled)
DATA_SOURCE=csv              # csv or scraper
DATABASE_PATH=data/licenses.db
```

## Authentication

API endpoints under `/api/*` are protected with an API key when `API_KEY` is set. The `/health` endpoint is always public.

Pass the key via the `X-API-Key` header:

```bash
curl -H "X-API-Key: your-secret-key" http://localhost:8000/api/license/1041069
```

If `API_KEY` is empty or unset, authentication is disabled and all endpoints are open.

For K8s, set via Helm:

```bash
helm install cslb-lookup ./helm/cslb-lookup --set secrets.apiKey=your-secret-key
```

## Project Structure

```
├── app/
│   ├── main.py              # FastAPI routes
│   ├── config.py            # Environment settings
│   ├── database.py          # SQLite queries
│   ├── models.py            # Pydantic models
│   ├── csv_loader.py        # CSV → SQLite import
│   ├── csv_downloader.py    # CSLB data portal downloader
│   ├── classifications.py   # CSLB code descriptions
│   └── scraper_client.py    # Direct HTTP scraper
├── scripts/
│   └── refresh_csv.sh       # Daily CSV download script
├── helm/
│   └── cslb-lookup/         # Helm chart
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```
