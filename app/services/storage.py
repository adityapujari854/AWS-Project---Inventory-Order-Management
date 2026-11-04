
"""Private S3 product-image storage with server-generated object keys."""

from dataclasses import dataclass
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.config import Settings, get_settings


class ImageStorageUnavailable(Exception):
    """Raised when S3 image storage is not configured."""


class ImageStorageError(Exception):
    """Raised when a configured S3 operation fails without exposing AWS internals."""


@dataclass(frozen=True)
class ValidatedImage:
    content: bytes
    content_type: str
    extension: str


class ProductImageStorage:
    """Uses the standard AWS credential provider chain, including EC2 instance roles."""

    def __init__(self, settings: Settings | None = None, client=None):
        self.settings = settings or get_settings()
        self._client = client

    @property
    def is_configured(self) -> bool:
        return self.settings.s3_image_storage_configured

    @property
    def client(self):
        if not self.is_configured:
            raise ImageStorageUnavailable("Image storage is not configured")

        if self._client is None:
            region = self.settings.aws_region

            self._client = boto3.client(
                "s3",
                region_name=region,
                endpoint_url=f"https://s3.{region}.amazonaws.com",
                config=Config(
                    signature_version="s3v4",
                    s3={"addressing_style": "virtual"},
                ),
            )

        return self._client

    def object_key(self, product_id: int, extension: str) -> str:
        prefix = (
            f"{self.settings.s3_product_image_prefix}/"
            if self.settings.s3_product_image_prefix
            else ""
        )
        return f"{prefix}products/{product_id}/{uuid4().hex}.{extension}"

    def upload(self, key: str, image: ValidatedImage) -> None:
        try:
            self.client.put_object(
                Bucket=self.settings.s3_bucket_name,
                Key=key,
                Body=image.content,
                ContentType=image.content_type,
                ServerSideEncryption="AES256",
            )
        except ImageStorageUnavailable:
            raise
        except (BotoCoreError, ClientError) as error:
            raise ImageStorageError("Image upload failed") from error

    def delete(self, key: str) -> None:
        try:
            self.client.delete_object(
                Bucket=self.settings.s3_bucket_name,
                Key=key,
            )
        except ImageStorageUnavailable:
            raise
        except (BotoCoreError, ClientError) as error:
            raise ImageStorageError("Image deletion failed") from error

    def presigned_url(self, key: str) -> str:
        try:
            return self.client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self.settings.s3_bucket_name,
                    "Key": key,
                },
                ExpiresIn=self.settings.s3_presigned_url_ttl_seconds,
            )
        except ImageStorageUnavailable:
            raise
        except (BotoCoreError, ClientError) as error:
            raise ImageStorageError(
                "Image access URL generation failed"
            ) from error


def validate_image(
    content: bytes,
    filename: str | None,
    content_type: str | None,
    max_size: int,
) -> ValidatedImage:
    """Validate extension, media type, size, and file signature before uploading."""

    if not content:
        raise ValueError("Image file is empty")

    if len(content) > max_size:
        raise ValueError(f"Image must be at most {max_size} bytes")

    filename = (filename or "").lower()
    content_type = (content_type or "").lower()

    image_types = {
        "jpg": (
            "image/jpeg",
            lambda data: data.startswith(b"\xff\xd8\xff"),
        ),
        "jpeg": (
            "image/jpeg",
            lambda data: data.startswith(b"\xff\xd8\xff"),
        ),
        "png": (
            "image/png",
            lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"),
        ),
        "webp": (
            "image/webp",
            lambda data: data.startswith(b"RIFF") and data[8:12] == b"WEBP",
        ),
    }

    extension = filename.rsplit(".", 1)[-1] if "." in filename else ""
    expected = image_types.get(extension)

    if (
        expected is None
        or content_type != expected[0]
        or not expected[1](content)
    ):
        raise ValueError("Only valid JPEG, PNG, and WebP image files are allowed")

    return ValidatedImage(
        content=content,
        content_type=content_type,
        extension=extension,
    )


def get_product_image_storage() -> ProductImageStorage:
    """Dependency factory; does not contact AWS until an image operation is requested."""
    return ProductImageStorage()
