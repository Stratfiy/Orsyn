"""Environment-driven settings. All variables use the ORSYN_ prefix."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ORSYN_", env_file=".env", extra="ignore")

    env: Literal["local", "dev", "prod"] = "local"
    log_level: str = "INFO"
    git_sha: str = "dev"
    ai_provider: Literal["fake"] = "fake"

    @property
    def docs_enabled(self) -> bool:
        """OpenAPI docs are served in local and dev only."""
        return self.env in ("local", "dev")


def get_settings() -> Settings:
    return Settings()
