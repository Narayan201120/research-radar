from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Research Radar API"
    database_url: str = (
        "postgresql+psycopg://research:research@postgres:5432/research_radar"
    )
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    openalex_mailto: str = "research-radar@example.com"
    openalex_topic_cv_id: str = "T10531"
    openalex_topic_llm_id: str = "T10181"
    ingest_interval_hours: float = 24.0
    scheduler_retry_minutes: float = 5.0
    scheduler_backoff_max_minutes: float = 60.0
    recovery_limit: int = 20
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    similarity_backend: str = "embeddings"  # tfidf | embeddings (default semantic; tfidf via env for revert)

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()