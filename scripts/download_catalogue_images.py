"""Restartable, attribution-safe Wikimedia Commons catalogue image downloader."""

import argparse
import html
from io import BytesIO
from http.client import IncompleteRead
import json
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PIL import Image

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.catalogue import EXTRA_PRODUCTS, SAMPLE_PRODUCTS

API = "https://commons.wikimedia.org/w/api.php"
OUTPUT = Path("app/static/images/products")
MANIFEST = OUTPUT / "manifest.json"
SOURCES = Path("SOURCES.md")
USER_AGENT = "InventoryHubCatalogueImageSeeder/3.0 (local catalogue maintenance)"
MIN_DELAY_SECONDS = 4
MAX_ATTEMPTS = 5
ACCEPTED_LICENSES = ("CC0", "CC BY", "CC-BY", "PUBLIC DOMAIN", "PD")
REJECTED_LICENSE_TERMS = ("NC", "ND", "ALL RIGHTS", "FAIR USE", "NONFREE")

# Fictional catalogue names do not identify real Commons files. These terms keep
# automated searches anchored to the product type rather than unrelated names.
SEARCH_TERMS = {
    "WM-001": "computer mouse", "KB-101": "computer keyboard", "WB-102": "webcam",
    "UD-103": "USB docking station", "LS-104": "laptop stand", "SSD-201": "NVMe SSD",
    "RAM-202": "DDR4 DIMM memory", "PSU-203": "ATX power supply", "FAN-204": "120mm computer fan",
    "RTR-301": "Wi-Fi router", "SWT-302": "gigabit Ethernet switch", "WAP-303": "wireless access point",
    "CAB-304": "Cat6 Ethernet cable", "MON-401": "LCD monitor", "MON-402": "QHD monitor",
    "MON-403": "ultrawide monitor", "MON-402": "computer monitor", "HDM-404": "HDMI cable", "AUD-501": "headset microphone",
    "AUD-503": "USB microphone", "AUD-504": "USB audio adapter", "OFF-601": "copy paper",
    "OFF-602": "office chair", "OFF-603": "document tray", "OFF-604": "marker pen",
    "CPU-701": "Intel Core processor", "CPU-702": "Intel Core processor", "CPU-703": "AMD Ryzen processor",
    "GPU-711": "NVIDIA GeForce graphics card", "GPU-712": "NVIDIA GeForce graphics card",
    "GPU-713": "workstation graphics card", "MB-721": "Micro-ATX motherboard", "MB-722": "ATX motherboard",
    "MB-723": "Mini-ITX motherboard", "MEM-731": "DDR5 DIMM memory", "MEM-733": "DDR5 DIMM memory",
    "STO-741": "SATA SSD", "STO-742": "external hard drive", "COL-753": "computer cooling fan",
    "NET-762": "USB Ethernet adapter", "DSP-763": "4K display", "CAM-766": "USB webcam camera",
    "AUD-764": "conference room speakerphone", "OFF-765": "cable management",
}
REJECTED_TITLE_TERMS = ("pdf", "panorama", "glitched", "garbled", "defective", "lighter", "failure")
GENERIC_SEARCH_TERMS = {"computer", "wireless", "usb", "office", "room", "audio", "camera", "display", "network"}


def text_value(metadata: dict, key: str) -> str:
    value = metadata.get(key, {})
    value = value.get("value", "") if isinstance(value, dict) else value
    return re.sub(r"<[^>]+>", "", html.unescape(str(value))).strip()


def is_reusable_license(name: str) -> bool:
    upper = name.upper().replace("-", " ")
    return bool(name) and any(value.replace("-", " ") in upper for value in ACCEPTED_LICENSES) and not any(
        value in upper for value in REJECTED_LICENSE_TERMS
    )


def delay_and_open(url: str) -> bytes:
    """Fetch with a delay and exponential backoff for transient failures."""
    error: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        if attempt:
            wait_seconds = MIN_DELAY_SECONDS * (2 ** (attempt - 1))
            print(f"  retry {attempt + 1}/{MAX_ATTEMPTS}; waiting {wait_seconds}s", flush=True)
            time.sleep(wait_seconds)
        else:
            time.sleep(MIN_DELAY_SECONDS)
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=30) as response:
                return response.read()
        except HTTPError as exc:
            error = exc
            if exc.code not in (429,) and not 500 <= exc.code < 600:
                break
        except URLError as exc:
            error = exc
        except IncompleteRead as exc:
            error = exc
    raise RuntimeError(str(error))


def request_json(params: dict) -> dict:
    return json.loads(delay_and_open(f"{API}?{urlencode(params)}"))


def extension_for(content: bytes) -> str | None:
    if content.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "webp"
    return None


def existing_image(sku: str) -> Path | None:
    for extension in ("webp", "jpg", "png"):
        path = OUTPUT / f"{sku}.{extension}"
        if path.is_file() and extension_for(path.read_bytes()[:16]) == extension:
            return path
    return None


def relevant(page_title: str, search_terms: str) -> bool:
    title = page_title.lower()
    if any(term in title for term in REJECTED_TITLE_TERMS):
        return False
    anchors = [
        word.lower() for word in re.findall(r"[a-zA-Z0-9]{3,}", search_terms)
        if word.lower() not in GENERIC_SEARCH_TERMS
    ]
    return any(anchor in title for anchor in anchors)


def find_image(search_terms: str) -> dict | None:
    data = request_json({
        "action": "query", "generator": "search", "gsrsearch": search_terms,
        "gsrnamespace": 6, "gsrlimit": 20, "prop": "imageinfo",
        "iiprop": "url|extmetadata", "iiurlwidth": 960, "format": "json",
    })
    candidates = []
    for page in data.get("query", {}).get("pages", {}).values():
        if not relevant(page.get("title", ""), search_terms):
            continue
        info = page.get("imageinfo", [{}])[0]
        metadata = info.get("extmetadata", {})
        license_name = text_value(metadata, "LicenseShortName")
        url = info.get("thumburl") or info.get("url")
        if url and is_reusable_license(license_name):
            score = sum(word.lower() in page.get("title", "").lower() for word in search_terms.split())
            candidates.append((score, page, info, metadata, license_name, url))
    if not candidates:
        return None
    _, page, info, metadata, license_name, url = max(candidates, key=lambda row: row[0])
    return {
        "source_page": f"https://commons.wikimedia.org/?curid={page['pageid']}",
        "image_url": url,
        "author": text_value(metadata, "Artist") or "Not listed",
        "license": license_name,
        "license_url": text_value(metadata, "LicenseUrl") or "See source page",
        "source_title": page.get("title", ""),
        "source_width": info.get("width"),
        "source_height": info.get("height"),
    }


def optimize(content: bytes, extension: str) -> tuple[bytes, str]:
    """Normalize downloaded files to a web-sized JPEG while retaining signatures."""
    with Image.open(BytesIO(content)) as image:
        image = image.convert("RGB")
        image.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
        output = BytesIO()
        image.save(output, format="JPEG", quality=86, optimize=True)
        return output.getvalue(), "jpg"


def write_fallback() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "fallback.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="700" height="500"><rect width="100%" height="100%" fill="#e9edfa"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#5067d9" font-family="sans-serif" font-size="32">Product image unavailable</text></svg>',
        encoding="utf-8",
    )


def write_sources(manifest: dict, products: list[tuple]) -> None:
    names = {row[0]: row[1] for row in products}
    lines = ["# Catalogue image sources", "", "Images below were downloaded and content-validated from Wikimedia Commons.", ""]
    for sku, source in sorted(manifest.items()):
        if not isinstance(source, dict) or not {"filename", "source_page", "image_url", "author", "license", "license_url"}.issubset(source):
            continue
        match = source.get("match_type", "preserved")
        lines.append(
            f"- `{source['filename']}` — {names.get(sku, sku)} ({match}); "
            f"[source page]({source['source_page']}); image: {source['image_url']}; "
            f"author: {source['author']}; licence: {source['license']} ({source['license_url']})"
        )
    missing = [sku for sku in {row[0] for row in products} if sku not in manifest]
    lines += ["", "## Fallback or unavailable products", ""]
    lines += [f"- `{sku}` — local fallback until a relevant reusable image is available." for sku in sorted(missing)]
    SOURCES.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replace", action="store_true", help="Replace valid existing SKU images.")
    parser.add_argument("--sku", action="append", help="Process only this SKU; may be repeated.")
    args = parser.parse_args()
    write_fallback()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    products = [row for row in SAMPLE_PRODUCTS + EXTRA_PRODUCTS if not args.sku or row[0] in args.sku]
    report = {"downloaded": [], "skipped": [], "unavailable": [], "failed": []}
    for index, (sku, name, *_) in enumerate(products, start=1):
        print(f"[{index}/{len(products)}] {sku} — {name}", flush=True)
        existing = existing_image(sku)
        if existing and not args.replace:
            if isinstance(manifest.get(sku), dict) and manifest[sku].get("filename") == existing.name:
                report["skipped"].append(sku)
                print("  SKIPPED (manifest)", flush=True)
                continue
        terms = SEARCH_TERMS.get(sku, name)
        try:
            candidate = find_image(terms)
            if candidate is None:
                report["unavailable"].append(sku)
                print("  UNAVAILABLE", flush=True)
                continue
            content = delay_and_open(candidate["image_url"])
            extension = extension_for(content)
            if extension is None:
                raise ValueError("unsupported or invalid image content")
            optimized, output_extension = optimize(content, extension)
            if extension_for(optimized) != output_extension:
                raise ValueError("optimized image failed signature validation")
            path = OUTPUT / f"{sku}.{output_extension}"
            temporary = path.with_suffix(".tmp")
            temporary.write_bytes(optimized)
            temporary.replace(path)
            candidate.update(filename=path.name, match_type="exact" if sku.lower() in candidate["source_title"].lower() else "representative", search_terms=terms)
            manifest[sku] = candidate
            report["downloaded"].append(sku)
            print(f"  DOWNLOADED ({path.name})", flush=True)
        except Exception as error:
            report["failed"].append(f"{sku}: {error}")
            print(f"  FAILED: {error}", flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_sources(manifest, products)
    print(json.dumps({key: len(value) for key, value in report.items()}, indent=2), flush=True)
    if report["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
