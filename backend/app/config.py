from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://deep_research:deep_research@localhost:5432/deep_research"
    clerk_issuer: str | None = None
    clerk_jwks_url: str | None = None
    clerk_secret_key: str | None = None
    cors_origins: str = "http://localhost:5173"
    auth_disabled: bool = False
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    tavily_api_key: str | None = None
    worker_poll_interval_seconds: float = 2.0
    max_subagents_per_run: int = 3
    max_search_results_per_subtask: int = 4

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
