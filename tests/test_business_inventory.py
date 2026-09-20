import json

from scripts.business_inventory import inventory_status, mark_previewed, select_item


def _queued(root, slug, lane, created_at, topic_id=None):
    directory = root / "business" / "inventory" / slug
    directory.mkdir(parents=True)
    topic_id = topic_id or slug
    (directory / "content.json").write_text(
        json.dumps(
            {
                "lane": lane,
                "topic_id": topic_id,
                "topic_title": f"Topic {slug}",
            }
        ),
        encoding="utf-8",
    )
    (directory / "ready.json").write_text(
        json.dumps(
            {
                "status": "READY",
                "lane": lane,
                "topic_id": topic_id,
                "created_at": created_at,
            }
        ),
        encoding="utf-8",
    )
    return directory


def test_business_inventory_counts_and_deficits(tmp_path):
    _queued(tmp_path, "day-a", "day", "2026-09-14T08:00:00Z")
    _queued(tmp_path, "evening-a", "evening", "2026-09-14T09:00:00Z")
    status = inventory_status(tmp_path)
    assert status["ready_total"] == 2
    assert status["deficits"] == {"day": 4, "evening": 4}


def test_business_inventory_selects_oldest_in_lane(tmp_path):
    _queued(tmp_path, "new", "day", "2026-09-14T09:00:00Z")
    old = _queued(tmp_path, "old", "day", "2026-09-14T08:00:00Z")
    _queued(tmp_path, "evening", "evening", "2026-09-14T07:00:00Z")
    assert select_item("day", tmp_path)["directory"] == old


def test_business_inventory_selects_oldest_across_lanes(tmp_path):
    _queued(tmp_path, "day", "day", "2026-09-14T09:00:00Z")
    oldest = _queued(tmp_path, "evening", "evening", "2026-09-14T07:00:00Z")
    assert select_item(root=tmp_path)["directory"] == oldest


def test_business_inventory_mark_previewed(tmp_path):
    directory = _queued(tmp_path, "day-a", "day", "2026-09-14T08:00:00Z")
    previewed = mark_previewed(directory, "456")
    assert not (directory / "ready.json").exists()
    payload = json.loads(previewed.read_text(encoding="utf-8"))
    assert payload["status"] == "PREVIEW_SENT"
    assert payload["github_run_id"] == "456"
    assert inventory_status(tmp_path)["ready_total"] == 0


def test_business_inventory_rejects_repeated_topic_id(tmp_path):
    _queued(tmp_path, "first", "day", "2026-09-14T08:00:00Z", "same-topic")
    _queued(tmp_path, "second", "evening", "2026-09-14T09:00:00Z", "same-topic")
    try:
        inventory_status(tmp_path)
    except SystemExit as exc:
        assert "repeated topic_id" in str(exc)
    else:
        raise AssertionError("duplicate business topics must block the queue")
