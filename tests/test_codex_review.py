import json
from src.codex_review import save_review


def test_review_request_is_pending_not_approval(tmp_path):
    result = save_review(tmp_path, publication_key="biz-test", content_hash="abc",
                         run_id=123, account="dramrou.business")
    assert result["status"] == "PENDING_APPROVAL"
    assert result["requires_explicit_user_approval"] is True
    assert result["approval_channel"] == "codex"
    assert json.loads((tmp_path / "codex_review.json").read_text()) == result


def test_pharmacy_existing_identity_needs_no_product_url(tmp_path, monkeypatch):
    from scripts import send_curated_preview as preview
    for number in range(1, 4):
        (tmp_path / f"slide{number:02}.png").touch()
    (tmp_path / "caption.txt").write_text("Test caption")
    (tmp_path / "product.json").write_text(json.dumps({"product_id": "existing-id"}))
    monkeypatch.setattr(preview, "ROOT", tmp_path)
    monkeypatch.setenv("CURATED_DIR", ".")
    monkeypatch.setenv("GITHUB_RUN_ID", "local-test")
    monkeypatch.setattr(preview, "assert_guardrails", lambda: None)
    monkeypatch.setattr(preview, "require_approved_qc", lambda *args: None)
    monkeypatch.setattr(preview, "quality_contract_metadata", lambda *args: {})
    monkeypatch.setattr(preview, "load_yaml", lambda *args: {"brand": "test"})
    monkeypatch.setattr(preview, "freeze_manifest", lambda *args: {"content_hash": "testhash"})
    preview.main()
    request = json.loads((tmp_path / "codex_review.json").read_text())
    assert request["account"] == "dramrouaboubakr"
    assert request["status"] == "PENDING_APPROVAL"
