"""Environment-driven settings. All variables use the ORSYN_ prefix."""

from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ORSYN_", env_file=".env", extra="ignore")

    env: Literal["local", "dev", "prod"] = "local"
    log_level: str = "INFO"
    git_sha: str = "dev"
    ai_provider: Literal["fake"] = "fake"
    # KYC provider (ORSYN_VERIFICATION_PROVIDER). Only "fake" exists today, so prod is
    # deliberately unbootable until a real provider is added: KYC must never run on
    # fake data in prod. Add the real provider to this Literal when it lands.
    verification_provider: Literal["fake"] = "fake"

    @model_validator(mode="after")
    def _no_fake_kyc_in_prod(self) -> "Settings":
        if self.env == "prod" and self.verification_provider == "fake":
            raise ValueError("verification_provider 'fake' is not allowed when env is 'prod'")
        return self

    @property
    def docs_enabled(self) -> bool:
        """OpenAPI docs are served in local and dev only."""
        return self.env in ("local", "dev")


def get_settings() -> Settings:
    return Settings()
