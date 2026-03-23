import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.core.logger import Logger
from app.models.schemas import SyncBundle, SyncStatus

logger = Logger().get_logger()

router = APIRouter(prefix="/sync", tags=["sync"])


@dataclass
class _SyncState:
    last_served: dict | None = None
    total_requests: int = 0


_state = _SyncState()


async def _fetch_gallery(
    client: httpx.AsyncClient,
    username: str,
) -> tuple[str, list[list[float]]]:
    """Fetch a single user's gallery. Returns (username, embeddings)."""
    try:
        resp = await client.get(
            f"{settings.VECTOR_OPERATION_URL}/vectors/{username}/gallery",
            params={"include_embeddings": "true"},
        )
        if resp.status_code == 200:
            data = resp.json()
            vectors = data.get("vectors", [])
            return username, [
                v["embedding"] for v in vectors if v.get("embedding")
            ]
    except Exception:
        logger.warning("Failed to fetch gallery for %s", username)
    return username, []


@router.get("/bundle", response_model=SyncBundle)
async def get_bundle(
    current_version: int = Query(
        0, description="Edge device's current version"
    ),
    offset: int = Query(0, ge=0, description="User offset for pagination"),
    limit: int = Query(
        settings.SYNC_PAGE_SIZE,
        ge=1,
        le=200,
        description="Max users per page",
    ),
) -> SyncBundle:
    """Edge devices call this to pull the latest sync bundle.

    Supports pagination via ``offset`` and ``limit`` query params.
    Edge should keep pulling while ``has_more`` is ``true``.

    Flow:
      1. GET /confidence/latest from Confidence Tuning → threshold + version.
      2. If cloud version <= current_version → return empty (no update).
      3. GET /vectors/drift-signals from Vector Operation → user list.
      4. Slice user list by offset/limit, fetch galleries concurrently.
      5. Return bundle page for edge to apply.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Get latest threshold
        try:
            resp = await client.get(
                f"{settings.CONFIDENCE_TUNNING_URL}/confidence/latest"
            )
            resp.raise_for_status()
            threshold_data = resp.json()
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to get threshold: {exc}",
            ) from exc

        version = threshold_data["version"]
        threshold = threshold_data["threshold"]

        # 2. Skip if edge is already up-to-date
        if version <= current_version:
            return SyncBundle(
                version=version,
                threshold=threshold,
                users_synced=0,
            )

        # 3. Get user list from drift signals
        try:
            resp = await client.get(
                f"{settings.VECTOR_OPERATION_URL}/vectors/drift-signals"
            )
            resp.raise_for_status()
            drift_data = resp.json()
            usernames = [s["username"] for s in drift_data.get("signals", [])]
        except Exception:
            logger.warning(
                "Failed to get drift signals, using empty user list"
            )
            usernames = []

        # 4. Paginate and fetch galleries concurrently
        page = usernames[offset : offset + limit]
        has_more = (offset + limit) < len(usernames)

        results = await asyncio.gather(
            *[_fetch_gallery(client, u) for u in page]
        )
        gallery = {name: vecs for name, vecs in results if vecs}

    _state.total_requests += 1
    _state.last_served = {
        "version": version,
        "threshold": threshold,
        "served_at": datetime.now(timezone.utc).isoformat(),
    }

    return SyncBundle(
        version=version,
        threshold=threshold,
        gallery=gallery,
        users_synced=len(gallery),
        has_more=has_more,
    )


@router.get("/status", response_model=SyncStatus)
async def sync_status() -> SyncStatus:
    """Return the current sync service status."""
    return SyncStatus(
        last_served_at=(
            _state.last_served["served_at"] if _state.last_served else None
        ),
        last_version=(
            _state.last_served["version"] if _state.last_served else None
        ),
        last_threshold=(
            _state.last_served["threshold"] if _state.last_served else None
        ),
        total_requests_served=_state.total_requests,
    )
