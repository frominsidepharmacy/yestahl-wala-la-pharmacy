"""Persist a review request alongside immutable media; never publish or message."""
import json
from pathlib import Path


def save_review(directory: Path, *, publication_key, content_hash, run_id, account):
    request = {
        "status": "PENDING_APPROVAL", "approval_channel": "codex",
        "publication_key": publication_key, "content_hash": content_hash,
        "artifact_run_id": str(run_id), "account": account,
        "requires_explicit_user_approval": True,
    }
    (directory / "codex_review.json").write_text(
        json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(request, ensure_ascii=False))
    return request
