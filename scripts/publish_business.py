#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from src.approval import verify_manifest
from src.config import assert_guardrails
from src.instagram import InstagramPublisher
from src.publishing import validate_public_urls
from src.telegram import TelegramClient


parser = argparse.ArgumentParser()
parser.add_argument("--publication-key", required=True)
parser.add_argument("--expected-hash", required=True)
parser.add_argument("--pending-dir", required=True)
args = parser.parse_args()

assert_guardrails()
if not args.publication_key.startswith("biz-"):
    raise SystemExit("Business publishing refuses a non-business publication key")
pending = Path(args.pending_dir)
manifest = json.loads((pending / "manifest.json").read_text(encoding="utf-8"))
if manifest.get("metadata", {}).get("account") != "business.by.dr_amrou":
    raise SystemExit("Business manifest account mismatch")
if not manifest["content_hash"].startswith(args.expected_hash) or not verify_manifest(pending):
    raise SystemExit("⚠️ النسخة اتغيرت بعد الموافقة، محتاجة موافقة جديدة.")

base = os.environ["PAGES_BASE_URL"].rstrip("/")
urls = [f"{base}/media/{args.publication_key}/{name}" for name in manifest["slides"]]
validate_public_urls(urls)
publisher = InstagramPublisher()
publisher.validate_account()
marker = f"#ref_{args.publication_key.replace('-', '_')}"
existing = publisher.find_by_caption_marker(marker)
if existing:
    result = {"already_published": True, "media_id": existing.get("id"), "permalink": existing.get("permalink")}
else:
    children = [publisher.create_child(url) for url in urls]
    for child in children:
        publisher.wait_ready(child)
    parent = publisher.create_carousel(children, f"{manifest['caption']}\n\n{marker}")
    publisher.wait_ready(parent)
    media_id = publisher.publish(parent)
    result = {"already_published": False, "media_id": media_id, "permalink": publisher.permalink(media_id)}

if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
    TelegramClient().call(
        "sendMessage",
        chat_id=os.environ["TELEGRAM_CHAT_ID"],
        text=f"✅ تم نشر كاروسيل «من جوة البيزنس» على @business.by_dr_amrou بعد موافقتك.\nالرابط: {result.get('permalink') or 'غير متاح'}",
        disable_web_page_preview=True,
    )
print(json.dumps(result, ensure_ascii=False))
