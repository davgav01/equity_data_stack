"""Configuration settings for equity_data_stack."""

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    data_root: Path = Field(default=Path("./DATA_ROOT"), alias="DATA_ROOT")
    polygon_api_key: SecretStr | None = Field(default=None, alias="POLYGON_API_KEY")
    massive_access_key: SecretStr | None = Field(
        default=None, alias="MASSIVE_ACCESS_KEY"
    )
    massive_secret_key: SecretStr | None = Field(
        default=None, alias="MASSIVE_SECRET_KEY"
    )
    massive_s3_endpoint: str | None = Field(default=None, alias="MASSIVE_S3_ENDPOINT")
    massive_s3_bucket: str | None = Field(default=None, alias="MASSIVE_S3_BUCKET")
    massive_s3_prefix: str | None = Field(default=None, alias="MASSIVE_S3_PREFIX")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        extra="ignore",
    )

    def ensure_data_root(self) -> None:
        """Create the data root directory if it does not exist."""
        self.data_root.mkdir(parents=True, exist_ok=True)
