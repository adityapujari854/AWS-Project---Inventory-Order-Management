"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Small dependency-free settings object for the first application phase."""

    def __init__(self) -> None:
        self.app_name = os.getenv("APP_NAME", "InventoryHub")
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./inventory.db")
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def database_path(self) -> Path | None:
        if not self.is_sqlite or self.database_url == "sqlite:///:memory:":
            return None
        return Path(self.database_url.removeprefix("sqlite:///"))


@lru_cache
def get_settings() -> Settings:
    """Return cached settings so all application components use one configuration."""
    return Settings()
