"""Configuration settings for equity_data_stack."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    data_root: Path = Field(default=Path("./data"), alias="DATA_ROOT")
    polygon_api_key: str | None = Field(default=None, alias="POLYGON_API_KEY")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        extra="ignore",
    )

    def ensure_data_root(self) -> None:
        """Create the data root directory if it does not exist."""
        self.data_root.mkdir(parents=True, exist_ok=True)
