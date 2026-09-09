#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from src.approval import freeze_manifest
from src.config import ROOT, assert_guardrails, load_yaml
from src.telegram import TelegramClient, inline_keyboard


def main() -> None:
    assert_guardrails()
    source = ROOT / os.environ.get("CURATED_DIR", "curated/cosrx-salicylic-cleanser-v1")
    slides = [source / f"slide{number:02d}.png" for number in range(1, 7)]
    missing = [path.name for path in slides if not path.exists()]
    if missing:
        raise SystemExit(f"Missing curated slides: {', '.join(missing)}")

    caption = (source / "caption.txt").read_text(encoding="utf-8").strip()
    product = json.loads((source / "product.json").read_text(encoding="utf-8"))
    metadata = {
        "brand": load_yaml("settings.yaml")["brand"],
        "product": product,
        "score": 69.0,
        "verdict": "يستاهل بشروط",
        "version": 1,
        "curated": True,
        "review_status": "READY_FOR_USER_REVIEW",
    }
    manifest = freeze_manifest(source, slides, caption, metadata)
    product_id = product["product_id"][:8]
    publication_key = f"{datetime.now(timezone.utc):%y%m%d}-k-{product_id}"
    run_id = os.environ["GITHUB_RUN_ID"]
    control = f"""━━━━━━━━━━
🎨 النسخة المعتمدة بصريًا للمراجعة

المنتج: {product['product_name']}
الفئة: Skin Care — Teal / Mint
الحكم: يستاهل بشروط
الإصدار: v1

راجع السلايدات والكابشن، ثم اختر الإجراء المناسب.
لن يتم النشر إلا بعد ضغطك على APPROVE & PUBLISH.
━━━━━━━━━━"""
    TelegramClient().send_preview_files(
        slides,
        control,
        caption,
        inline_keyboard(publication_key, 1, manifest["content_hash"], run_id),
    )
    print(json.dumps({
        "status": "PENDING_APPROVAL",
        "publication_key": publication_key,
        "content_hash_prefix": manifest["content_hash"][:12],
        "artifact_run_id": run_id,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
