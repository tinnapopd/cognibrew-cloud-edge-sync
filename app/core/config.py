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

    # Upstream services
    CONFIDENCE_TUNING_URL: str = "http://localhost:8003"
    VECTOR_OPERATION_URL: str = "http://localhost:8002"

    # Sync pagination
    SYNC_PAGE_SIZE: int = 50


settings = Settings()  # type: ignore
