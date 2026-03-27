from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import QdrantDep
from app.core.config import settings
from app.core.logger import Logger
from app.core.qdrant import get_vectors_by_device_id, insert_vector
from app.models.schemas import (
    SyncBundle,
    SyncUpdateRequest,
    SyncUpdateResponse,
)

logger = Logger().get_logger()

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/update", response_model=SyncUpdateResponse)
async def sync_update(
    client: QdrantDep, payload: SyncUpdateRequest
) -> SyncUpdateResponse:
    try:
        insert_vector(
            client=client,
            device_id=payload.device_id,
            threshold=payload.threshold,
            username=payload.username,
            embedding=payload.embedding,
        )
    except Exception as e:
        logger.exception(
            "sync_update_failed: device=%s user=%s",
            payload.device_id,
            payload.username,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Failed to persist vector to Qdrant: {e}",
        )

    return SyncUpdateResponse(
        device_id=payload.device_id,
        username=payload.username,
    )


@router.get("/bundle", response_model=SyncBundle)
async def get_bundle(
    client: QdrantDep,
    device_id: str = Query(..., description="Device ID to pull bundle for"),
    offset: int = Query(0, ge=0, description="User offset for pagination"),
    limit: int = Query(
        settings.SYNC_PAGE_SIZE,
        ge=1,
        le=200,
        description="Max users per page",
    ),
    since: Optional[str] = Query(
        None,
        description="Only return data processed on or after this "
        + "date (YYYY-MM-DD)",
    ),
) -> SyncBundle:
    """Edge devices call this to pull the latest sync bundle.

    Reads vectors and threshold from Qdrant. Supports pagination via
    ``offset`` and ``limit`` query params. Edge should keep pulling
    while ``has_more`` (on-edge) is ``true``.

    """
    try:
        vectors = get_vectors_by_device_id(
            client=client,
            device_id=device_id,
            since=since,
        )
    except Exception as e:
        logger.exception("sync_bundle_fetch_failed: device=%s", device_id)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch vectors from Qdrant: {e}",
        )

    # Group vectors by username into a gallery
    gallery = {}
    threshold = 0.0
    for vec in vectors:
        username = vec["username"]
        if username not in gallery:
            gallery[username] = []

        # Update
        gallery[username].append(vec["embedding"])
        threshold += vec["threshold"]

    avg_threshold = threshold / len(vectors) if vectors else 0.5

    # Paginate users
    usernames = sorted(gallery.keys())
    page = usernames[offset : offset + limit]
    has_more = (offset + limit) < len(usernames)
    paged_gallery = {u: gallery[u] for u in page}

    return SyncBundle(
        threshold=avg_threshold,
        gallery=paged_gallery,
        users_synced=len(paged_gallery),
        has_more=has_more,
    )
