"""Verify that locally served catalogue images are safe to use.

The application deliberately displays only manifest-listed files. This utility
checks that each one belongs to a catalogue SKU, exists below the static images
directory, has a supported extension and has matching image magic bytes.
"""

from __future__ import annotations

import json
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.catalogue import EXTRA_PRODUCTS, SAMPLE_PRODUCTS


ROOT = Path("app/static/images/products")
MANIFEST = ROOT / "manifest.json"
SOURCES = Path("SOURCES.md")
SUPPORTED = {".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff", ".png": b"\x89PNG\r\n\x1a\n", ".webp": b"RIFF"}
REQUIRED_METADATA = ("filename", "source_page", "image_url", "license")


def valid_image(path: Path) -> bool:
    header = path.read_bytes()[:12]
    if path.suffix.lower() == ".webp":
        return header.startswith(SUPPORTED[".webp"]) and header[8:12] == b"WEBP"
    return header.startswith(SUPPORTED.get(path.suffix.lower(), b""))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-complete", action="store_true", help="Fail when any catalogue SKU lacks a verified local image.")
    args = parser.parse_args()
    catalogue = {row[0] for row in [*SAMPLE_PRODUCTS, *EXTRA_PRODUCTS]}
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    source_text = SOURCES.read_text(encoding="utf-8")
    invalid: list[str] = []
    verified: list[str] = []

    for sku, entry in manifest.items():
        if sku not in catalogue or not isinstance(entry, dict) or any(not isinstance(entry.get(key), str) or not entry[key].strip() for key in REQUIRED_METADATA):
            invalid.append(f"{sku}: invalid manifest metadata")
            continue
        filename = entry["filename"]
        path = ROOT / filename
        if not filename.upper().startswith(f"{sku}.") or Path(filename).name != filename or path.suffix.lower() not in SUPPORTED or not path.is_file() or not valid_image(path):
            invalid.append(f"{sku}: missing or invalid image {filename}")
            continue
        if f"`{filename}`" not in source_text:
            invalid.append(f"{sku}: missing SOURCES.md attribution")
            continue
        verified.append(sku)

    missing = sorted(catalogue - set(verified))
    report = {
        "catalogue_products": len(catalogue),
        "manifest_entries": len(manifest),
        "verified_images": len(verified),
        "fallback_products": len(missing),
        "missing_images": missing,
        "invalid_entries": invalid,
        "verified_skus": sorted(verified),
    }
    print(json.dumps(report, indent=2))
    return 1 if invalid or (args.require_complete and missing) else 0


if __name__ == "__main__":
    raise SystemExit(main())
