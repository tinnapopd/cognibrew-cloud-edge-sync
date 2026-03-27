from pydantic import BaseModel, Field


class SyncUpdateRequest(BaseModel):
    device_id: str
    threshold: float
    username: str
    embedding: list[float]


class SyncUpdateResponse(BaseModel):
    status: str = "ok"
    device_id: str
    username: str


class SyncBundle(BaseModel):
    threshold: float
    gallery: dict[str, list[list[float]]] = Field(
        default_factory=dict,
        description="Per-user gallery: {username: [[512-dim], ...]}",
    )
    users_synced: int
    has_more: bool = Field(
        False, description="True if more pages are available"
    )
