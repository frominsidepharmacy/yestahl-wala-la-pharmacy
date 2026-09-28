from __future__ import annotations

import json
import hashlib
from datetime import datetime
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

QUALITY_CONTRACT_VERSION = 2
REFERENCE_CONTRACTS = {
    "chatgpt-imagegen-reference": {
        "reference_id": "pharmacy-torn-paper-editorial-v1",
        "reference_sha256": "2602973a447dbb85f83c007e0d2eba23053ae65118751dbe108242b7fcb43192",
    },
    "chatgpt-imagegen-business-reference": {
        "reference_id": "business-premium-cartoon-office-v1",
        "reference_sha256": "92820ceff2f823bd2bcb2ff0aa0b06c1c2c103f68631500d74c699b0bc48b2d3",
    },
}


def reference_contract_error(source: Path) -> str | None:
    """Return why an inventory item is not locked to the retained reference."""
    provenance_path = source / "design_provenance.json"
    if not provenance_path.exists():
        return "missing design_provenance.json"
    try:
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return "invalid design_provenance.json"

    if provenance.get("quality_contract_version") != QUALITY_CONTRACT_VERSION:
        return f"quality_contract_version must be {QUALITY_CONTRACT_VERSION}"
    renderer_id = provenance.get("renderer_id")
    contract = REFERENCE_CONTRACTS.get(renderer_id)
    if contract is None:
        return "unapproved design renderer"
    if provenance.get("renderer_version") != 2:
        return "renderer_version must be 2"
    for field, expected in contract.items():
        if provenance.get(field) != expected:
            return f"{field} does not match the retained reference"

    review = provenance.get("visual_review")
    if not isinstance(review, dict):
        return "missing visual_review"
    expected_review = {
        "status": "PASS",
        "method": "side_by_side",
        "reference_match": "PASS",
        "text_legibility": "PASS",
        "brand_match": "PASS",
    }
    for field, expected in expected_review.items():
        if review.get(field) != expected:
            return f"visual_review.{field} must be {expected}"
    if not str(review.get("reviewer") or "").strip():
        return "visual_review.reviewer is required"
    try:
        reviewed_at = datetime.fromisoformat(
            str(review.get("reviewed_at") or "").replace("Z", "+00:00")
        )
    except ValueError:
        return "visual_review.reviewed_at must be ISO-8601"
    if reviewed_at.tzinfo is None:
        return "visual_review.reviewed_at must include a timezone"
    return None


def quality_contract_metadata(source: Path) -> dict:
    error = reference_contract_error(source)
    if error:
        raise SystemExit(f"QC BLOCK: {error}")
    provenance = json.loads(
        (source / "design_provenance.json").read_text(encoding="utf-8")
    )
    return {
        "quality_contract_version": QUALITY_CONTRACT_VERSION,
        "reference_id": provenance["reference_id"],
        "reference_sha256": provenance["reference_sha256"],
        "renderer_id": provenance["renderer_id"],
    }


def require_approved_qc(source: Path, slides: list[Path]) -> dict:
    """Block Telegram/publishing unless a complete, explicit visual-QC report passes."""
    report_path = source / "qc_report.json"
    if not report_path.exists():
        raise SystemExit(f"QC BLOCK: missing {report_path}")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("quality_contract_version") != QUALITY_CONTRACT_VERSION:
        raise SystemExit(
            f"QC BLOCK: quality_contract_version must be {QUALITY_CONTRACT_VERSION}"
        )
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

    if len(slides) != 3:
        raise SystemExit(f"QC BLOCK: expected exactly 3 slides, got {len(slides)}")
    for slide in slides:
        if not slide.exists():
            raise SystemExit(f"QC BLOCK: missing slide {slide}")
        with Image.open(slide) as image:
            if image.size != (1080, 1350):
                raise SystemExit(
                    f"QC BLOCK: {slide.name} is {image.size}, expected (1080, 1350)"
                )
    error = reference_contract_error(source)
    if error:
        raise SystemExit(f"QC BLOCK: {error}")
    provenance = json.loads(
        (source / "design_provenance.json").read_text(encoding="utf-8")
    )
    expected = provenance.get("slide_sha256", {})
    for slide in slides:
        actual = hashlib.sha256(slide.read_bytes()).hexdigest()
        if expected.get(slide.name) != actual:
            raise SystemExit(f"QC BLOCK: {slide.name} changed after locked rendering")
    return report
