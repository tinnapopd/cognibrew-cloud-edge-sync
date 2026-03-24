# CogniBrew Cloud Edge Sync

Aggregates optimal threshold and vector gallery from upstream cloud services. Edge devices pull sync bundles via a paginated REST API.

## Architecture

```
Edge Device ──poll──▶ Edge Sync ──fetch──▶ Confidence Tuning
                         │                  (threshold + version)
                         └──────fetch──▶ Vector Operation
                                          (user galleries)
```

Edge devices periodically call `GET /sync/bundle` to pull the latest data — the cloud never pushes.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/sync/bundle` | Pull latest threshold + gallery bundle (paginated) |
| `GET` | `/api/v1/sync/status` | Sync service status |
| `GET` | `/api/v1/utils/health-check/` | Health check |

### Pull Sync Bundle

```bash
# First page
curl "http://localhost:8000/api/v1/sync/bundle?current_version=0&offset=0&limit=50"

# Next page (if has_more=true)
curl "http://localhost:8000/api/v1/sync/bundle?current_version=0&offset=50&limit=50"
```

**Response:**

```json
{
  "version": 5,
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
    resp = httpx.get(
        f"{SYNC_URL}/api/v1/sync/bundle",
        params={"current_version": local_version, "offset": offset, "limit": 50},
    )
    bundle = resp.json()
    if bundle["users_synced"] > 0:
        apply_update(bundle)
    if not bundle["has_more"]:
        local_version = bundle["version"]
        break
    offset += 50
```

## Project Structure

```
.github/workflows/
└── ci.yml          # Lint + Docker build & push
app/
├── api/            # Route handlers
├── core/           # Config & logging
├── models/         # Pydantic schemas
├── main.py         # FastAPI application
└── pre_start.py    # Pre-startup script
scripts/
└── prestart.sh     # Docker container pre-start hook
```

## Development Setup

### Prerequisites

- Docker
- Python 3.10+

### Run the API

**With Docker:**

```bash
docker build -t cognibrew-sync .
docker run --name cognibrew-sync \
  -e CONFIDENCE_TUNING_URL=http://confidence:8003 \
  -e VECTOR_OPERATION_URL=http://vector:8002 \
  -e ENVIRONMENT=local \
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
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `ENVIRONMENT` | `local` | Runtime environment: `local`, `staging`, or `production` |
| `API_PREFIX_STR` | `/api/v1` | API route prefix |
| `PROJECT_NAME` | `CogniBrew Edge Sync` | Application name shown in docs |
| `CONFIDENCE_TUNING_URL` | `http://confidence-tuning:8003` | Confidence Tuning service URL |
| `VECTOR_OPERATION_URL` | `http://vector-operation:8002` | Vector Operation service URL |
| `SYNC_PAGE_SIZE` | `50` | Default number of users per bundle page |
