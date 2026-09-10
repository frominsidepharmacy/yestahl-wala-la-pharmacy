import json

import pytest
from PIL import Image

from src.curated_qc import REQUIRED_CHECKS, require_approved_qc


def _slides(tmp_path):
    paths = []
    for number in range(1, 7):
        path = tmp_path / f"slide{number:02d}.png"
        Image.new("RGB", (1080, 1350), "white").save(path)
        paths.append(path)
    return paths


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
    assert require_approved_qc(tmp_path, _slides(tmp_path)) == report
