#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from src.config import ROOT


LANE_TARGETS = {
    "day": 5,
    "evening": 5,
}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_created_at(value: str, marker_path: Path) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise SystemExit(
            f"BUSINESS QUEUE BLOCK: invalid created_at in {marker_path}"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise SystemExit(
            f"BUSINESS QUEUE BLOCK: created_at must be UTC in {marker_path}"
        )
    return value


def ready_items(root: Path = ROOT) -> list[dict]:
    items = []
    queue_root = root / "business" / "inventory"
    topic_directories: dict[str, list[Path]] = {}
    for content_path in sorted(queue_root.glob("*/content.json")):
        topic_id = str(_read_json(content_path).get("topic_id") or "").strip()
        if topic_id:
            topic_directories.setdefault(topic_id, []).append(content_path.parent)
    duplicates = {
        topic_id: directories
        for topic_id, directories in topic_directories.items()
        if len(directories) > 1
    }
    if duplicates:
        details = ", ".join(
            f"{topic_id} ({len(directories)})"
            for topic_id, directories in sorted(duplicates.items())
        )
        raise SystemExit(f"BUSINESS QUEUE BLOCK: repeated topic_id: {details}")

    for marker_path in sorted(queue_root.glob("*/ready.json")):
        marker = _read_json(marker_path)
        if marker.get("status") != "READY":
            raise SystemExit(
                f"BUSINESS QUEUE BLOCK: ready marker status is not READY in {marker_path}"
            )
        content_path = marker_path.parent / "content.json"
        if not content_path.exists():
            raise SystemExit(f"BUSINESS QUEUE BLOCK: missing {content_path}")
        content = _read_json(content_path)
        lane = marker.get("lane") or content.get("lane")
        if lane not in LANE_TARGETS:
            raise SystemExit(
                f"BUSINESS QUEUE BLOCK: unsupported lane in {marker_path}: {lane}"
            )
        if content.get("lane") != lane:
            raise SystemExit(
                f"BUSINESS QUEUE BLOCK: lane mismatch in {marker_path.parent}"
            )
        topic_id = marker.get("topic_id") or content.get("topic_id")
        if not topic_id:
            raise SystemExit(
                f"BUSINESS QUEUE BLOCK: missing topic_id in {marker_path.parent}"
            )
        created_at = _validate_created_at(marker.get("created_at"), marker_path)
        items.append(
            {
                "directory": marker_path.parent,
                "lane": lane,
                "topic_id": str(topic_id),
                "created_at": created_at,
            }
        )
    return items


def inventory_status(root: Path = ROOT) -> dict:
    counts = {lane: 0 for lane in LANE_TARGETS}
    for item in ready_items(root):
        counts[item["lane"]] += 1
    deficits = {
        lane: max(0, target - counts[lane])
        for lane, target in LANE_TARGETS.items()
    }
    return {
        "target_total": sum(LANE_TARGETS.values()),
        "ready_total": sum(counts.values()),
        "targets": LANE_TARGETS,
        "counts": counts,
        "deficits": deficits,
        "missing_total": sum(deficits.values()),
    }


def select_item(lane: str, root: Path = ROOT) -> dict | None:
    candidates = [item for item in ready_items(root) if item["lane"] == lane]
    if not candidates:
        return None
    return min(candidates, key=lambda item: (item["created_at"], item["directory"].name))


def mark_previewed(directory: Path, run_id: str) -> Path:
    ready_path = directory / "ready.json"
    if not ready_path.exists():
        raise SystemExit(f"BUSINESS QUEUE BLOCK: missing {ready_path}")
    payload = _read_json(ready_path)
    payload.update(
        {
            "status": "PREVIEW_SENT",
            "previewed_at": datetime.now(timezone.utc).isoformat(),
            "github_run_id": str(run_id),
        }
    )
    previewed_path = directory / "previewed.json"
    previewed_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    ready_path.unlink()
    return previewed_path


def _write_github_output(values: dict) -> None:
    output_path = os.getenv("GITHUB_OUTPUT")
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage the isolated business carousel inventory."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status")
    select_parser = subparsers.add_parser("select")
    select_parser.add_argument("--lane", required=True, choices=sorted(LANE_TARGETS))
    mark_parser = subparsers.add_parser("mark-previewed")
    mark_parser.add_argument("--directory", required=True)
    mark_parser.add_argument("--run-id", required=True)

    args = parser.parse_args()
    if args.command == "status":
        print(json.dumps(inventory_status(), ensure_ascii=False, indent=2))
        return
    if args.command == "select":
        item = select_item(args.lane)
        values = {
            "found": "true" if item else "false",
            "business_dir": (
                item["directory"].relative_to(ROOT).as_posix() if item else ""
            ),
        }
        _write_github_output(values)
        print(json.dumps(values, ensure_ascii=False))
        return

    directory = (ROOT / args.directory).resolve()
    inventory_root = (ROOT / "business" / "inventory").resolve()
    if inventory_root not in directory.parents or directory.parent != inventory_root:
        raise SystemExit(
            "BUSINESS QUEUE BLOCK: directory must be a direct child of business/inventory/"
        )
    print(mark_previewed(directory, args.run_id))


if __name__ == "__main__":
    main()
