from pydantic import BaseModel, Field


class SyncBundle(BaseModel):
    """Bundle returned to Edge devices when they pull updates."""

    version: int
    threshold: float
    gallery: dict[str, list[list[float]]] = Field(
        default_factory=dict,
        description="Per-user gallery: {username: [[512-dim], ...]}",
    )
    users_synced: int
    has_more: bool = Field(
        False, description="True if more pages are available"
    )


class SyncStatus(BaseModel):
    """Current sync service status."""

    last_served_at: str | None = None
    last_version: int | None = None
    last_threshold: float | None = None
    total_requests_served: int = 0
