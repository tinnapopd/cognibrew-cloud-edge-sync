from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        frozen=False,
        env_ignore_empty=True,
        case_sensitive=False,
    )
    API_PREFIX_STR: str = "/api/v1"
    PROJECT_NAME: str = "CogniBrew Edge Sync"
    ENVIRONMENT: Literal["local", "staging", "production"] = "production"

    # Sync pagination
    SYNC_PAGE_SIZE: int = 50

    # Qdrant
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6334
    QDRANT_COLLECTION: str = "sync_collection"
    EMBEDDING_DIM: int = 512


settings = Settings()  # type: ignore
