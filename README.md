# CogniBrew Cloud Edge Sync

Receives optimal thresholds and vector galleries from the Airflow pipeline and persists them in [Qdrant](https://qdrant.tech/). Edge devices pull sync bundles via a paginated REST API.

## Architecture

```
Airflow Pipeline (a single vector) --> POST /sync/update --> Edge Sync <-- GET /sync/bundle <-- Edge Device (pull loop)
```

The pipeline pushes per-user embeddings and thresholds; the service stores them as vectors in Qdrant. Edge devices pull bundles on their own schedule with built-in pagination.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/sync/update` | Receive threshold + vector from pipeline and persist to Qdrant |
| `GET` | `/api/v1/sync/bundle` | Pull latest threshold + gallery bundle (paginated, optional `since` filter) |
| `GET` | `/api/v1/utils/health-check/` | Health check |

### Push Sync Update (Pipeline → Edge Sync)

```bash
curl -X POST "http://localhost:8000/api/v1/sync/update" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "device-001",
    "threshold": 0.82,
    "username": "alice",
    "embedding": [0.1, 0.2, 0.3]
  }'
```

**Response:**

```json
{
  "status": "ok",
  "device_id": "device-001",
  "username": "alice"
}
```

### Pull Sync Bundle (Edge Device ← Edge Sync)

```bash
# First page
curl "http://localhost:8000/api/v1/sync/bundle?device_id=device-001&offset=0&limit=50"

# With date filter (only vectors processed on or after the given date)
curl "http://localhost:8000/api/v1/sync/bundle?device_id=device-001&offset=0&limit=50&since=2026-03-01"

# Next page (if has_more=true)
curl "http://localhost:8000/api/v1/sync/bundle?device_id=device-001&offset=50&limit=50"
```

**Response:**

```json
{
  "threshold": 0.82,
  "gallery": {
    "alice": [[0.1, 0.2, ...]],
    "bob": [[0.3, 0.4, ...]]
  },
  "users_synced": 2,
  "has_more": false
}
```

### Edge Device Pull Loop

```python
offset = 0
while True:
    resp = requests.get(
        f"{SYNC_URL}/api/v1/sync/bundle",
        params={"device_id": DEVICE_ID, "offset": offset, "limit": 50},
    )
    bundle = resp.json()
    if bundle["users_synced"] > 0:
        apply_update(bundle)
    if not bundle["has_more"]:
        break
    offset += 50
```

## Project Structure

```
.github/workflows/
└── ci.yml              # Lint + Docker build & push
app/
├── api/
│   ├── deps.py         # QdrantClient dependency injection (QdrantDep)
│   ├── main.py         # API router aggregation
│   └── routes/
│       ├── sync.py     # POST /sync/update, GET /sync/bundle
│       └── utils.py    # GET /utils/health-check
├── core/
│   ├── config.py       # Pydantic Settings (env-driven configuration)
│   ├── logger.py       # Singleton JSON logger (python-json-logger)
│   ├── qdrant.py       # Collection init, vector CRUD (insert, scroll, filter)
│   └── security.py     # Security utilities
├── models/
│   └── schemas.py      # Pydantic request/response schemas
├── main.py             # FastAPI app with lifespan (Qdrant collection init)
└── pre_start.py        # Pre-startup script
scripts/
├── init_qdrant.sh      # Launch local Qdrant via Docker, wait for readiness
└── prestart.sh         # Docker container pre-start hook
```

## Development Setup

### Prerequisites

- Docker
- Python 3.10+

### Start Qdrant

Use the provided helper script to launch a local Qdrant instance:

```bash
./scripts/init_qdrant.sh
```

> Set `SKIP_DOCKER=1` if Qdrant is already running.

### Run the API

**With Docker:**

```bash
docker build -t cognibrew-sync .
docker run --name cognibrew-sync \
  -e ENVIRONMENT=local \
  -e QDRANT_HOST=host.docker.internal \
  -p 8000:8000 \
  cognibrew-sync
```

**Without Docker:**

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Open API Docs

Visit [http://localhost:8000/docs](http://localhost:8000/docs) for interactive Swagger documentation.

## CI/CD

GitHub Actions pipeline (`.github/workflows/ci.yml`):

| Job | Trigger | Description |
|-----|---------|-------------|
| **Lint** | PR to `main`, push to `main`, tags | Runs [Ruff](https://docs.astral.sh/ruff/) linter |
| **Build & Push** | Tags matching `v*` | Builds Docker image and pushes to Docker Hub |

### Image Tags

```
<DOCKERHUB_USERNAME>/actions:cognibrew-cloud-edge-sync-v1.0.0-abc1234
<DOCKERHUB_USERNAME>/actions:cognibrew-cloud-edge-sync-latest
```

### Required Secrets

| Secret | Description |
|--------|-------------|
| `DOCKERHUB_USERNAME` | Docker Hub username |
| `DOCKERHUB_TOKEN` | Docker Hub access token |

## Environment Variables

See [`.env.example`](.env.example) for all available configuration options.

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |
| `ENVIRONMENT` | `production` | Runtime environment: `local`, `staging`, or `production` |
| `API_PREFIX_STR` | `/api/v1` | API route prefix |
| `PROJECT_NAME` | `CogniBrew Edge Sync` | Application name shown in docs |
| `SYNC_PAGE_SIZE` | `50` | Default number of users per bundle page |
| `QDRANT_HOST` | `localhost` | Qdrant server hostname |
| `QDRANT_PORT` | `6334` | Qdrant gRPC port |
| `QDRANT_COLLECTION` | `sync_collection` | Qdrant collection name |
| `EMBEDDING_DIM` | `512` | Dimensionality of face embeddings |
