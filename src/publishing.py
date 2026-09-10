from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import time
import requests
from src.approval import verify_manifest
from src.history import History
from src.instagram import InstagramPublisher


def prepare_approved_site(pending_dir: Path, site_dir: Path, publication_key: str, expected_hash: str) -> Path:
    manifest = json.loads((pending_dir / "manifest.json").read_text(encoding="utf-8"))
    if not manifest["content_hash"].startswith(expected_hash) or not verify_manifest(pending_dir):
        raise RuntimeError("⚠️ النسخة اتغيرت بعد الموافقة، محتاجة موافقة جديدة.")
    target = site_dir / "media" / publication_key
    target.mkdir(parents=True, exist_ok=True)
    for name in manifest["slides"]:
        shutil.copy2(pending_dir / name, target / name)
    return target


def validate_public_urls(urls, session=None, timeout: int = 0, interval: int = 5):
    client = session or requests.Session()
    for url in urls:
        deadline = time.monotonic() + timeout
        last_status = None
        last_content_type = ""
        while True:
            response = client.head(url, timeout=20, allow_redirects=True)
            last_status = response.status_code
            last_content_type = response.headers.get("content-type", "")
            if last_status == 200 and last_content_type.startswith("image/"):
                break
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"media URL not ready after {timeout}s: {url} "
                    f"({last_status}, {last_content_type or 'no content-type'})"
                )
            time.sleep(interval)


def publish_once(publication_key: str, pending_dir: Path, image_urls, history: History = None, publisher=None):
    history = history or History()
    previous = history.publication_status(publication_key)
    if previous and previous[0] == "PUBLISHED":
        return {"already_published": True, "media_id": previous[1], "permalink": previous[2]}
    manifest = json.loads((pending_dir / "manifest.json").read_text(encoding="utf-8"))
    product_data = manifest["metadata"]["product"]
    from src.models import Product
    product_data.pop("product_id", None)
    product = Product(**product_data)
    history.upsert(publication_key, product, "PUBLISHING", content_hash=manifest["content_hash"])
    publisher = publisher or InstagramPublisher()
    try:
        marker = f"#ref_{publication_key.replace('-', '_')}"
        existing = publisher.find_by_caption_marker(marker)
        if existing:
            history.upsert(publication_key, product, "PUBLISHED", content_hash=manifest["content_hash"],
                           published_at=datetime.now(timezone.utc).isoformat(), instagram_media_id=existing.get("id"),
                           instagram_permalink=existing.get("permalink"))
            return {"already_published": True, "media_id": existing.get("id"), "permalink": existing.get("permalink")}
        children = [publisher.create_child(url) for url in image_urls]
        for child in children:
            publisher.wait_ready(child)
        parent = publisher.create_carousel(children, f"{manifest['caption']}\n\n{marker}")
        publisher.wait_ready(parent)
        media_id = publisher.publish(parent)
        permalink = publisher.permalink(media_id)
        history.upsert(publication_key, product, "PUBLISHED", content_hash=manifest["content_hash"],
                       published_at=datetime.now(timezone.utc).isoformat(), instagram_media_id=media_id,
                       instagram_permalink=permalink)
        return {"already_published": False, "media_id": media_id, "permalink": permalink}
    except Exception:
        history.upsert(publication_key, product, "PUBLISH_FAILED_SAFE", content_hash=manifest["content_hash"])
        raise
