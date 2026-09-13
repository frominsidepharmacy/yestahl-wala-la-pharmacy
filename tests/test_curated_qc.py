import json
import hashlib

import pytest
from PIL import Image

from src.curated_qc import REQUIRED_CHECKS, require_approved_qc


def _slides(tmp_path, count=6):
    paths = []
    for number in range(1, count + 1):
        path = tmp_path / f"slide{number:02d}.png"
        Image.new("RGB", (1080, 1350), "white").save(path)
        paths.append(path)
    return paths


def _provenance(tmp_path, paths):
    report = {
        "renderer_id": "men-gowa-el-saydalia-torn-paper",
        "renderer_version": 2,
        "dimensions": [1080, 1350],
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
        "overall_status": "PASS",
        "checks": {name: "PASS" for name in REQUIRED_CHECKS - {"reference_fidelity"}},
    }
    (tmp_path / "qc_report.json").write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(SystemExit, match="reference_fidelity"):
        require_approved_qc(tmp_path, _slides(tmp_path))


def test_passed_report_and_dimensions_allow_send(tmp_path):
    report = {
        "overall_status": "PASS",
        "checks": {name: "PASS" for name in REQUIRED_CHECKS},
    }
    (tmp_path / "qc_report.json").write_text(json.dumps(report), encoding="utf-8")
    slides = _slides(tmp_path)
    _provenance(tmp_path, slides)
    assert require_approved_qc(tmp_path, slides) == report


def test_missing_locked_reference_provenance_blocks_send(tmp_path):
    report = {
        "overall_status": "PASS",
        "checks": {name: "PASS" for name in REQUIRED_CHECKS},
    }
    (tmp_path / "qc_report.json").write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(SystemExit, match="locked-reference"):
        require_approved_qc(tmp_path, _slides(tmp_path))


def test_modified_slide_after_render_blocks_send(tmp_path):
    report = {
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
        "overall_status": "PASS",
        "checks": {name: "PASS" for name in REQUIRED_CHECKS},
    }
    (tmp_path / "qc_report.json").write_text(json.dumps(report), encoding="utf-8")
    slides = _slides(tmp_path, 3)
    provenance = {
        "renderer_id": "chatgpt-imagegen-reference",
        "renderer_version": 1,
        "dimensions": [1080, 1350],
        "slide_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in slides
        },
    }
    (tmp_path / "design_provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
    assert require_approved_qc(tmp_path, slides) == report
