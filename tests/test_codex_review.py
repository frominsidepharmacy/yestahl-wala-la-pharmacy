import json
from src.codex_review import save_review


def test_review_request_is_pending_not_approval(tmp_path):
    result = save_review(tmp_path, publication_key="biz-test", content_hash="abc",
                         run_id=123, account="dramrou.business")
    assert result["status"] == "PENDING_APPROVAL"
    assert result["requires_explicit_user_approval"] is True
    assert result["approval_channel"] == "codex"
    assert json.loads((tmp_path / "codex_review.json").read_text()) == result
