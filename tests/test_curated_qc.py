import json
import hashlib

import pytest
from PIL import Image

from src.curated_qc import (
    QUALITY_CONTRACT_VERSION,
    REFERENCE_CONTRACTS,
    REQUIRED_CHECKS,
    require_approved_qc,
)


def _slides(tmp_path, count=3):
    paths = []
    for number in range(1, count + 1):
        path = tmp_path / f"slide{number:02d}.png"
        Image.new("RGB", (1080, 1350), "white").save(path)
        paths.append(path)
    return paths


def _provenance(tmp_path, paths, renderer_id="chatgpt-imagegen-reference"):
    reference = REFERENCE_CONTRACTS[renderer_id]
    report = {
        "quality_contract_version": QUALITY_CONTRACT_VERSION,
        "renderer_id": renderer_id,
        "renderer_version": 2,
        **reference,
        "dimensions": [1080, 1350],
        "visual_review": {
            "status": "PASS",
            "method": "side_by_side",
            "reference_match": "PASS",
            "text_legibility": "PASS",
            "brand_match": "PASS",
            "reviewer": "test-reviewer",
            "reviewed_at": "2026-09-28T10:00:00Z",
        },
        "slide_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths
        },
    }
    (tmp_path / "design_provenance.json").write_text(json.dumps(report), encoding="utf-8")


def test_missing_report_blocks_send(tmp_path):
    with pytest.raises(SystemExit, match="QC BLOCK"):
        require_approved_qc(tmp_path, _slides(tmp_path))


def test_all_quality_checks_are_required(tmp_path):
    report = {
        "quality_contract_version": QUALITY_CONTRACT_VERSION,
        "overall_status": "PASS",
        "checks": {name: "PASS" for name in REQUIRED_CHECKS - {"reference_fidelity"}},
    }
    (tmp_path / "qc_report.json").write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(SystemExit, match="reference_fidelity"):
        require_approved_qc(tmp_path, _slides(tmp_path))


def test_passed_report_and_dimensions_allow_send(tmp_path):
    report = {
        "quality_contract_version": QUALITY_CONTRACT_VERSION,
        "overall_status": "PASS",
        "checks": {name: "PASS" for name in REQUIRED_CHECKS},
    }
    (tmp_path / "qc_report.json").write_text(json.dumps(report), encoding="utf-8")
    slides = _slides(tmp_path)
    _provenance(tmp_path, slides)
    assert require_approved_qc(tmp_path, slides) == report


def test_missing_locked_reference_provenance_blocks_send(tmp_path):
    report = {
        "quality_contract_version": QUALITY_CONTRACT_VERSION,
        "overall_status": "PASS",
        "checks": {name: "PASS" for name in REQUIRED_CHECKS},
    }
    (tmp_path / "qc_report.json").write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(SystemExit, match="design_provenance"):
        require_approved_qc(tmp_path, _slides(tmp_path))


def test_modified_slide_after_render_blocks_send(tmp_path):
    report = {
        "quality_contract_version": QUALITY_CONTRACT_VERSION,
        "overall_status": "PASS",
        "checks": {name: "PASS" for name in REQUIRED_CHECKS},
    }
    (tmp_path / "qc_report.json").write_text(json.dumps(report), encoding="utf-8")
    slides = _slides(tmp_path)
    _provenance(tmp_path, slides)
    Image.new("RGB", (1080, 1350), "black").save(slides[0])
    with pytest.raises(SystemExit, match="changed after locked rendering"):
        require_approved_qc(tmp_path, slides)


def test_three_slide_imagegen_carousel_is_supported(tmp_path):
    report = {
        "quality_contract_version": QUALITY_CONTRACT_VERSION,
        "overall_status": "PASS",
        "checks": {name: "PASS" for name in REQUIRED_CHECKS},
    }
    (tmp_path / "qc_report.json").write_text(json.dumps(report), encoding="utf-8")
    slides = _slides(tmp_path, 3)
    _provenance(tmp_path, slides)
    assert require_approved_qc(tmp_path, slides) == report


def test_six_slide_carousel_is_rejected(tmp_path):
    report = {
        "quality_contract_version": QUALITY_CONTRACT_VERSION,
        "overall_status": "PASS",
        "checks": {name: "PASS" for name in REQUIRED_CHECKS},
    }
    (tmp_path / "qc_report.json").write_text(json.dumps(report), encoding="utf-8")
    slides = _slides(tmp_path, 6)
    _provenance(tmp_path, slides, "chatgpt-imagegen-business-reference")
    with pytest.raises(SystemExit, match="exactly 3"):
        require_approved_qc(tmp_path, slides)


def test_three_slide_business_imagegen_carousel_is_supported(tmp_path):
    report = {
        "quality_contract_version": QUALITY_CONTRACT_VERSION,
        "overall_status": "PASS",
        "checks": {name: "PASS" for name in REQUIRED_CHECKS},
    }
    (tmp_path / "qc_report.json").write_text(json.dumps(report), encoding="utf-8")
    slides = _slides(tmp_path, 3)
    _provenance(tmp_path, slides, "chatgpt-imagegen-business-reference")
    assert require_approved_qc(tmp_path, slides) == report


def test_self_declared_pass_without_reference_hash_is_rejected(tmp_path):
    report = {
        "quality_contract_version": QUALITY_CONTRACT_VERSION,
        "overall_status": "PASS",
        "checks": {name: "PASS" for name in REQUIRED_CHECKS},
    }
    (tmp_path / "qc_report.json").write_text(json.dumps(report), encoding="utf-8")
    slides = _slides(tmp_path)
    _provenance(tmp_path, slides)
    provenance_path = tmp_path / "design_provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance.pop("reference_sha256")
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
    with pytest.raises(SystemExit, match="reference_sha256"):
        require_approved_qc(tmp_path, slides)
