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
        self.session_secret = os.getenv("SESSION_SECRET", "development-only-change-me")
        self.session_max_age_seconds = int(os.getenv("SESSION_MAX_AGE_SECONDS", "28800"))
        self.session_cookie_secure = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
        self.aws_region = os.getenv("AWS_REGION")
        self.s3_bucket_name = os.getenv("S3_BUCKET_NAME")
        self.s3_product_image_prefix = os.getenv("S3_PRODUCT_IMAGE_PREFIX", "product-images").strip("/")
        self.s3_presigned_url_ttl_seconds = int(os.getenv("S3_PRESIGNED_URL_TTL_SECONDS", "900"))
        self.s3_max_image_size_bytes = int(os.getenv("S3_MAX_IMAGE_SIZE_BYTES", "5242880"))

        if self.environment.lower() == "production":
            if self.database_url.startswith("sqlite"):
                raise ValueError("DATABASE_URL must point to a managed database in production")
            if len(self.session_secret) < 32 or self.session_secret.startswith("replace-with-") or self.session_secret == "development-only-change-me":
                raise ValueError("SESSION_SECRET must be a non-placeholder value of at least 32 characters in production")
            if not self.session_cookie_secure:
                raise ValueError("SESSION_COOKIE_SECURE must be true in production")

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def s3_image_storage_configured(self) -> bool:
        return bool(self.s3_bucket_name and self.aws_region)

    @property
    def database_path(self) -> Path | None:
        if not self.is_sqlite or self.database_url == "sqlite:///:memory:":
            return None
        return Path(self.database_url.removeprefix("sqlite:///"))


@lru_cache
def get_settings() -> Settings:
    """Return cached settings so all application components use one configuration."""
    return Settings()
