#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import hashlib
import shutil
from datetime import datetime, timezone

from src.approval import freeze_manifest
from src.config import ROOT, assert_guardrails
from src.curated_qc import require_approved_qc
from src.telegram import TelegramClient, inline_keyboard


LANES = {
    "day": {"label": "قصة إدارية كرتونية", "slot": "13:00"},
    "evening": {"label": "تحليل بيزنس كرتوني", "slot": "21:00"},
}


def main() -> None:
    assert_guardrails()
    source_value = os.environ.get("BUSINESS_CURATED_DIR", "")
    if not source_value:
        raise SystemExit("BUSINESS_CURATED_DIR is required")
    source = (ROOT / source_value).resolve()
    inventory_root = (ROOT / "business" / "inventory").resolve()
    if inventory_root not in source.parents or source.parent != inventory_root:
        raise SystemExit("Business source must be a direct child of business/inventory/")

    content_path = source / "content.json"
    if not content_path.exists():
        raise SystemExit(f"Missing business content: {content_path}")
    content = json.loads(content_path.read_text(encoding="utf-8"))
    lane = content.get("lane")
    if lane not in LANES:
        raise SystemExit(f"Unsupported business lane: {lane}")
    topic_id = str(content.get("topic_id") or "").strip()
    topic_title = str(content.get("topic_title") or "").strip()
    if not topic_id or not topic_title:
        raise SystemExit("Business content requires topic_id and topic_title")

    pending = ROOT / "business_pending" / source.name
    pending.mkdir(parents=True, exist_ok=True)
    source_slides = sorted(source.glob("slide[0-9][0-9].png"))
    if len(source_slides) != 6:
        raise SystemExit(f"Expected 6 business slides, found {len(source_slides)}")
    require_approved_qc(source, source_slides)
    slides = []
    for source_slide in source_slides:
        if not source_slide.exists():
            raise SystemExit(f"Missing business slide: {source_slide}")
        target = pending / source_slide.name
        shutil.copy2(source_slide, target)
        slides.append(target)

    caption = (source / "caption.txt").read_text(encoding="utf-8").strip()
    now = datetime.now(timezone.utc)
    safe_topic = "".join(ch for ch in topic_id.lower() if ch.isalnum())[:10]
    if not safe_topic:
        safe_topic = hashlib.sha256(topic_title.encode()).hexdigest()[:10]
    publication_key = f"biz-{now:%y%m%d}-{safe_topic}"
    metadata = {
        "account": "dramrou.business",
        "brand_line": "من جوة البيزنس | د. عمرو أبوبكر",
        "lane": lane,
        "topic_id": topic_id,
        "topic_title": topic_title,
        "slot_dubai": LANES[lane]["slot"],
        "publication_key": publication_key,
        "version": 1,
        "review_status": "READY_FOR_USER_REVIEW",
    }
    manifest = freeze_manifest(pending, slides, caption, metadata)
    run_id = os.environ["GITHUB_RUN_ID"]
    control = f"""━━━━━━━━━━
🎨 من جوة البيزنس | د. عمرو أبوبكر

الحساب: @dramrou.business
الموضوع: {topic_title}
النوع: {LANES[lane]['label']}
موعد النشر: {LANES[lane]['slot']} بتوقيت دبي
الإصدار: v1

راجع السلايدات والكابشن.
لن يتم النشر إلا بعد ضغطك على APPROVE & PUBLISH.
مسار «من جوة الصيدلية» منفصل ولن يتأثر.
━━━━━━━━━━"""
    TelegramClient().send_preview_files(
        slides,
        control,
        caption,
        inline_keyboard(publication_key, 1, manifest["content_hash"], run_id),
    )
    print(json.dumps({
        "status": "PENDING_APPROVAL",
        "account": "dramrou.business",
        "publication_key": publication_key,
        "topic_id": topic_id,
        "content_hash_prefix": manifest["content_hash"][:12],
        "artifact_run_id": run_id,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
