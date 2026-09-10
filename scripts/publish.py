#!/usr/bin/env python3
import argparse, json, os
from pathlib import Path
from src.approval import verify_manifest
from src.config import ROOT, assert_guardrails
from src.publishing import publish_once, validate_public_urls
from src.telegram import TelegramClient

parser = argparse.ArgumentParser()
parser.add_argument("--publication-key", required=True)
parser.add_argument("--expected-hash", required=True)
parser.add_argument("--pending-dir", required=True)
args = parser.parse_args()
assert_guardrails()
pending = Path(args.pending_dir)
manifest = json.loads((pending / "manifest.json").read_text(encoding="utf-8"))
if not manifest["content_hash"].startswith(args.expected_hash) or not verify_manifest(pending):
    raise SystemExit("⚠️ النسخة اتغيرت بعد الموافقة، محتاجة موافقة جديدة.")
base = os.environ["PAGES_BASE_URL"].rstrip("/")
urls = [f"{base}/media/{args.publication_key}/{name}" for name in manifest["slides"]]
validate_public_urls(urls, timeout=120)
result = publish_once(args.publication_key, pending, urls)
if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
    TelegramClient().send_publish_confirmation(
        "من جوة الصيدلية",
        "dramrouaboubakr",
        result.get("permalink"),
        result.get("already_published", False),
    )
print(json.dumps(result, ensure_ascii=False))
