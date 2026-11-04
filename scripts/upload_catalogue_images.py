"""Explicit, non-destructive bulk upload of validated catalogue images to private S3."""

import argparse
import json
from pathlib import Path
import sys

import boto3
from botocore.exceptions import ClientError
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import get_settings
from app.database import SessionLocal
from app.models.product import Product
from scripts.verify_catalogue_images import valid_image, ROOT, MANIFEST


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true", help="Perform uploads after displaying the dry-run summary.")
    args = parser.parse_args()
    settings = get_settings()
    if not settings.s3_image_storage_configured:
        raise SystemExit("AWS_REGION and S3_BUCKET_NAME must be configured")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    prefix = f"{settings.s3_product_image_prefix}/catalogue".strip("/")
    client = boto3.client("s3", region_name=settings.aws_region)
    with SessionLocal() as db:
        products = {product.sku: product for product in db.scalars(select(Product)).all()}
    actions = []
    for sku, entry in sorted(manifest.items()):
        filename = entry.get("filename", "") if isinstance(entry, dict) else ""
        path = ROOT / filename
        if sku not in products or not path.is_file() or not valid_image(path):
            continue
        if products[sku].image_key:
            actions.append((sku, "skip-user-upload", f"existing product image: {products[sku].image_key}"))
            continue
        key = f"{prefix}/{filename}"
        try:
            client.head_object(Bucket=settings.s3_bucket_name, Key=key)
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                actions.append((sku, "upload", key))
            else:
                raise
        else:
            actions.append((sku, "skip-existing", key))

    print("S3 catalogue upload dry run")
    for sku, action, detail in actions:
        print(f"- {sku}: {action} ({detail})")
    uploads = [(sku, detail) for sku, action, detail in actions if action == "upload"]
    print(f"Would upload {len(uploads)} image(s); no existing objects or user images will be overwritten.")
    if not args.confirm:
        print("Dry run only. Re-run with --confirm to upload.")
        return 0
    for sku, key in uploads:
        path = ROOT / manifest[sku]["filename"]
        client.upload_file(str(path), settings.s3_bucket_name, key, ExtraArgs={"ContentType": "image/jpeg", "ServerSideEncryption": "AES256"})
        print(f"Uploaded {sku} -> s3://{settings.s3_bucket_name}/{key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
