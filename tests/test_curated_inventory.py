import json

from src.curated_qc import QUALITY_CONTRACT_VERSION, REFERENCE_CONTRACTS

from scripts.curated_inventory import inventory_status, mark_previewed, select_item


def _queued(root, slug, category, created_at):
    directory = root / "curated" / slug
    directory.mkdir(parents=True)
    (directory / "product.json").write_text(
        json.dumps({"category": category}), encoding="utf-8"
    )
    (directory / "ready.json").write_text(
        json.dumps({"category": category, "created_at": created_at}), encoding="utf-8"
    )
    reference = REFERENCE_CONTRACTS["chatgpt-imagegen-reference"]
    (directory / "design_provenance.json").write_text(
        json.dumps({
            "quality_contract_version": QUALITY_CONTRACT_VERSION,
            "renderer_id": "chatgpt-imagegen-reference",
            "renderer_version": 2,
            **reference,
            "visual_review": {
                "status": "PASS", "method": "side_by_side",
                "reference_match": "PASS", "text_legibility": "PASS",
                "brand_match": "PASS", "reviewer": "test",
                "reviewed_at": "2026-09-28T10:00:00Z",
            },
        }), encoding="utf-8"
    )
    return directory


def test_inventory_counts_and_deficits(tmp_path):
    _queued(tmp_path, "skin-a", "korean_skincare", "2026-09-13T08:00:00Z")
    _queued(tmp_path, "vitamin-a", "vitamins_supplements", "2026-09-13T09:00:00Z")
    status = inventory_status(tmp_path)
    assert status["ready_total"] == 2
    assert status["deficits"] == {
        "korean_skincare": 3,
        "vitamins_supplements": 2,
        "personal_care": 3,
    }


def test_selects_oldest_ready_item_in_category(tmp_path):
    _queued(tmp_path, "skin-new", "korean_skincare", "2026-09-13T09:00:00Z")
    old = _queued(tmp_path, "skin-old", "korean_skincare", "2026-09-13T08:00:00Z")
    _queued(tmp_path, "personal", "personal_care", "2026-09-13T07:00:00Z")
    assert select_item("korean_skincare", tmp_path)["directory"] == old


def test_selects_oldest_ready_item_across_categories(tmp_path):
    _queued(tmp_path, "skin", "korean_skincare", "2026-09-13T09:00:00Z")
    oldest = _queued(tmp_path, "personal", "personal_care", "2026-09-13T07:00:00Z")
    _queued(tmp_path, "vitamin", "vitamins_supplements", "2026-09-13T08:00:00Z")
    assert select_item(root=tmp_path)["directory"] == oldest


def test_mark_previewed_removes_item_from_ready_inventory(tmp_path):
    directory = _queued(tmp_path, "vitamin-a", "vitamins_supplements", "2026-09-13T09:00:00Z")
    previewed = mark_previewed(directory, "123")
    assert not (directory / "ready.json").exists()
    payload = json.loads(previewed.read_text(encoding="utf-8"))
    assert payload["status"] == "PREVIEW_SENT"
    assert payload["github_run_id"] == "123"
    assert inventory_status(tmp_path)["ready_total"] == 0


def test_legacy_self_declared_pass_is_not_counted(tmp_path):
    directory = _queued(tmp_path, "legacy", "korean_skincare", "2026-09-13T08:00:00Z")
    provenance = json.loads((directory / "design_provenance.json").read_text())
    provenance.pop("reference_sha256")
    (directory / "design_provenance.json").write_text(json.dumps(provenance))
    assert inventory_status(tmp_path)["ready_total"] == 0
