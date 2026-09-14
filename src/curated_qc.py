from __future__ import annotations

import json
import hashlib
from pathlib import Path

from PIL import Image


REQUIRED_CHECKS = {
    "arabic_text_fidelity",
    "reference_fidelity",
    "brand_identity",
    "layout_readability",
    "visual_integrity",
    "content_accuracy",
}


def require_approved_qc(source: Path, slides: list[Path]) -> dict:
    """Block Telegram/publishing unless a complete, explicit visual-QC report passes."""
    report_path = source / "qc_report.json"
    if not report_path.exists():
        raise SystemExit(f"QC BLOCK: missing {report_path}")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("overall_status") != "PASS":
        raise SystemExit("QC BLOCK: overall_status is not PASS")

    checks = report.get("checks", {})
    missing = sorted(REQUIRED_CHECKS - set(checks))
    failed = sorted(name for name in REQUIRED_CHECKS if checks.get(name) != "PASS")
    if missing or failed:
        raise SystemExit(
            "QC BLOCK: incomplete/failed checks; "
            f"missing={missing or 'none'} failed={failed or 'none'}"
        )

    if len(slides) not in {3, 6}:
        raise SystemExit(f"QC BLOCK: expected 3 or 6 slides, got {len(slides)}")
    for slide in slides:
        if not slide.exists():
            raise SystemExit(f"QC BLOCK: missing slide {slide}")
        with Image.open(slide) as image:
            if image.size != (1080, 1350):
                raise SystemExit(
                    f"QC BLOCK: {slide.name} is {image.size}, expected (1080, 1350)"
                )
    provenance_path = source / "design_provenance.json"
    if not provenance_path.exists():
        raise SystemExit("QC BLOCK: missing locked-reference design provenance")
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    approved_renderers = {
        "men-gowa-el-saydalia-torn-paper": {6},
        "chatgpt-imagegen-reference": {3, 6},
        "chatgpt-imagegen-business-reference": {6},
    }
    renderer_id = provenance.get("renderer_id")
    if renderer_id not in approved_renderers:
        raise SystemExit("QC BLOCK: unapproved design renderer")
    if renderer_id == "men-gowa-el-saydalia-torn-paper" and provenance.get("renderer_version") != 2:
        raise SystemExit("QC BLOCK: unapproved design renderer version")
    if len(slides) not in approved_renderers[renderer_id]:
        raise SystemExit("QC BLOCK: renderer does not support this slide count")
    expected = provenance.get("slide_sha256", {})
    for slide in slides:
        actual = hashlib.sha256(slide.read_bytes()).hexdigest()
        if expected.get(slide.name) != actual:
            raise SystemExit(f"QC BLOCK: {slide.name} changed after locked rendering")
    return report
