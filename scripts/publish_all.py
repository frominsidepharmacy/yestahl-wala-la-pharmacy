#!/usr/bin/env python3
import json, os
from pathlib import Path
from src.publishing import publish_once, validate_public_urls
from src.telegram import TelegramClient

base = os.environ["PAGES_BASE_URL"].rstrip("/")
results = []
for manifest_path in sorted(Path("approved").glob("*/manifest.json")):
    directory, key = manifest_path.parent, manifest_path.parent.name
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    urls = [f"{base}/media/{key}/{name}" for name in manifest["slides"]]
    validate_public_urls(urls)
    results.append({"publication_key": key, **publish_once(key, directory, urls)})
if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
    telegram = TelegramClient()
    for result in results:
        telegram.send_publish_confirmation(
            "من جوة الصيدلية",
            "dramrouaboubakr",
            result.get("permalink"),
            result.get("already_published", False),
        )
print(json.dumps(results, ensure_ascii=False))
