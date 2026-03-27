from datetime import datetime, timezone
from typing import Dict, List, Optional
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.core.config import settings
from app.core.logger import Logger

logger = Logger().get_logger()


def _device_filter(device_id: str) -> Filter:
    """Return a Qdrant filter for device_id."""
    return Filter(
        must=[
            FieldCondition(
                key="device_id",
                match=MatchValue(value=device_id),
            )
        ]
    )


def init_collection(*, client: QdrantClient) -> None:
    existing = {col.name for col in client.get_collections().collections}
    if settings.QDRANT_COLLECTION not in existing:
        client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(
                size=settings.EMBEDDING_DIM,
                distance=Distance.COSINE,
            ),
        )
        logger.info(
            "qdrant_collection_created: %s", settings.QDRANT_COLLECTION
        )


def get_vectors_by_device_id(
    *,
    client: QdrantClient,
    device_id: str,
    since: Optional[str] = None,
) -> List[Dict]:
    """
    Retrieve vectors for a device, optionally filtered by date.

    Args:
        client: Qdrant client instance (injected via QdrantDep).
        device_id: Target device.
        since: If provided, only return vectors with ``date >= since``.

    Returns:
        List of vectors with format: [
            {
                "device_id": str,
                "threshold": float,
                "username": str,
                "embedding": [float, ...]
            },
            ...
        ]
    """
    # Use scroll to paginate through the vectors
    results = []
    offset = None
    while True:
        points, next_offset = client.scroll(
            collection_name=settings.QDRANT_COLLECTION,
            scroll_filter=_device_filter(device_id),
            limit=100,
            offset=offset,
            with_vectors=True,
        )
        for point in points:
            payload = point.payload
            if payload is None:
                continue

            # Filter by date in Python (payload date is a string)
            if since and payload.get("date", "") < since:
                continue

            results.append(
                {
                    "device_id": payload["device_id"],
                    "threshold": payload["threshold"],
                    "username": payload["username"],
                    "embedding": point.vector,
                }
            )

        if next_offset is None:
            break

        offset = next_offset
    return results


def insert_vector(
    *,
    client: QdrantClient,
    device_id: str,
    threshold: float,
    username: str,
    embedding: List[float],
) -> None:
    """Insert a single vector with metadata into Qdrant."""
    client.upsert(
        collection_name=settings.QDRANT_COLLECTION,
        points=[
            PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "device_id": device_id,
                    "threshold": threshold,
                    "username": username,
                    "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                },
            )
        ],
    )
