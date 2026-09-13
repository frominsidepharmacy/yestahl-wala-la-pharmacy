#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from src.config import ROOT


CATEGORY_TARGETS = {
    "korean_skincare": 4,
    "vitamins_supplements": 3,
    "personal_care": 3,
}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def ready_items(root: Path = ROOT) -> list[dict]:
    items = []
    for marker_path in sorted((root / "curated").glob("*/ready.json")):
        marker = _read_json(marker_path)
        product_path = marker_path.parent / "product.json"
        if not product_path.exists():
            raise SystemExit(f"QUEUE BLOCK: missing {product_path}")
        product = _read_json(product_path)
        category = marker.get("category") or product.get("category")
        if category not in CATEGORY_TARGETS:
            raise SystemExit(f"QUEUE BLOCK: unsupported category in {marker_path}: {category}")
        if product.get("category") != category:
            raise SystemExit(f"QUEUE BLOCK: category mismatch in {marker_path.parent}")
        items.append({
            "directory": marker_path.parent,
            "category": category,
            "created_at": marker.get("created_at", "9999-12-31T23:59:59Z"),
        })
    return items


def inventory_status(root: Path = ROOT) -> dict:
    counts = {category: 0 for category in CATEGORY_TARGETS}
    for item in ready_items(root):
        counts[item["category"]] += 1
    deficits = {
        category: max(0, target - counts[category])
        for category, target in CATEGORY_TARGETS.items()
    }
    return {
        "target_total": sum(CATEGORY_TARGETS.values()),
        "ready_total": sum(counts.values()),
        "targets": CATEGORY_TARGETS,
        "counts": counts,
        "deficits": deficits,
        "missing_total": sum(deficits.values()),
    }


def select_item(category: str, root: Path = ROOT) -> dict | None:
    candidates = [item for item in ready_items(root) if item["category"] == category]
    if not candidates:
        return None
    return min(candidates, key=lambda item: (item["created_at"], item["directory"].name))


def mark_previewed(directory: Path, run_id: str) -> Path:
    ready_path = directory / "ready.json"
    if not ready_path.exists():
        raise SystemExit(f"QUEUE BLOCK: missing {ready_path}")
    payload = _read_json(ready_path)
    payload.update({
        "status": "PREVIEW_SENT",
        "previewed_at": datetime.now(timezone.utc).isoformat(),
        "github_run_id": str(run_id),
    })
    previewed_path = directory / "previewed.json"
    previewed_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
    parser = argparse.ArgumentParser(description="Manage the curated pharmacy carousel inventory.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status")
    select_parser = subparsers.add_parser("select")
    select_parser.add_argument("--category", required=True, choices=sorted(CATEGORY_TARGETS))
    mark_parser = subparsers.add_parser("mark-previewed")
    mark_parser.add_argument("--directory", required=True)
    mark_parser.add_argument("--run-id", required=True)

    args = parser.parse_args()
    if args.command == "status":
        print(json.dumps(inventory_status(), ensure_ascii=False, indent=2))
        return
    if args.command == "select":
        item = select_item(args.category)
        values = {
            "found": "true" if item else "false",
            "curated_dir": item["directory"].relative_to(ROOT).as_posix() if item else "",
        }
        _write_github_output(values)
        print(json.dumps(values, ensure_ascii=False))
        return
    directory = (ROOT / args.directory).resolve()
    if ROOT.resolve() not in directory.parents or directory.parent != (ROOT / "curated").resolve():
        raise SystemExit("QUEUE BLOCK: directory must be a direct child of curated/")
    print(mark_previewed(directory, args.run_id))


if __name__ == "__main__":
    main()
