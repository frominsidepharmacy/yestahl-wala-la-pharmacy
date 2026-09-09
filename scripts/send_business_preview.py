#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from zoneinfo import ZoneInfo

from src.approval import freeze_manifest
from src.config import ROOT, assert_guardrails
from src.telegram import TelegramClient, inline_keyboard


STYLES = {
    "cartoon-he-said": {"label": "كرتوني ساخر — هو قال… بس هو يقصد", "slot": "13:00"},
    "editorial-focus": {"label": "Editorial — حماية التركيز", "slot": "21:00"},
}


def main() -> None:
    assert_guardrails()
    style = os.environ.get("BUSINESS_STYLE", "cartoon-he-said")
    if style not in STYLES:
        raise SystemExit(f"Unsupported BUSINESS_STYLE: {style}")

    source = ROOT / "business" / "curated" / style
    pending = ROOT / "business_pending" / style
    pending.mkdir(parents=True, exist_ok=True)
    slides = []
    for number in range(1, 7):
        source_slide = source / f"slide{number:02d}.png"
        if not source_slide.exists():
            raise SystemExit(f"Missing business slide: {source_slide}")
        target = pending / source_slide.name
        shutil.copy2(source_slide, target)
        slides.append(target)

    caption = (source / "caption.txt").read_text(encoding="utf-8").strip()
    now = datetime.now(ZoneInfo("Asia/Dubai"))
    short_style = "cartoon" if style == "cartoon-he-said" else "editorial"
    publication_key = f"biz-{now:%y%m%d}-{short_style}"
    metadata = {
        "account": "business.by.dr_amrou",
        "brand_line": "من جوة البيزنس | د. عمرو أبوبكر",
        "style": style,
        "slot_dubai": STYLES[style]["slot"],
        "publication_key": publication_key,
        "version": 2,
        "review_status": "READY_FOR_USER_REVIEW",
    }
    manifest = freeze_manifest(pending, slides, caption, metadata)
    run_id = os.environ["GITHUB_RUN_ID"]
    control = f"""━━━━━━━━━━
🎨 من جوة البيزنس | د. عمرو أبوبكر

الحساب: @business.by_dr_amrou
النوع: {STYLES[style]['label']}
موعد النشر: {STYLES[style]['slot']} بتوقيت دبي
الإصدار: v2

راجع السلايدات والكابشن.
لن يتم النشر إلا بعد ضغطك على APPROVE & PUBLISH.
مسار «من جوة الصيدلية» منفصل ولن يتأثر.
━━━━━━━━━━"""
    TelegramClient().send_preview_files(
        slides,
        control,
        caption,
        inline_keyboard(publication_key, 2, manifest["content_hash"], run_id),
    )
    print(json.dumps({
        "status": "PENDING_APPROVAL",
        "account": "business.by.dr_amrou",
        "publication_key": publication_key,
        "content_hash_prefix": manifest["content_hash"][:12],
        "artifact_run_id": run_id,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
