from __future__ import annotations

import json
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

    if len(slides) != 6:
        raise SystemExit(f"QC BLOCK: expected 6 slides, got {len(slides)}")
    for slide in slides:
        if not slide.exists():
            raise SystemExit(f"QC BLOCK: missing slide {slide}")
        with Image.open(slide) as image:
            if image.size != (1080, 1350):
                raise SystemExit(
                    f"QC BLOCK: {slide.name} is {image.size}, expected (1080, 1350)"
                )
    return report
