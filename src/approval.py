from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List
from src.models import stable_hash


def calculate_version_hash(slide_paths: List[Path], caption: str, metadata: Dict) -> str:
    return stable_hash([p.read_bytes() for p in slide_paths], caption, metadata)


def freeze_manifest(directory: Path, slide_paths: List[Path], caption: str, metadata: Dict) -> Dict:
    content_hash = calculate_version_hash(slide_paths, caption, metadata)
    manifest = {"content_hash": content_hash, "slides": [p.name for p in slide_paths], "caption": caption, "metadata": metadata}
    (directory / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def verify_manifest(directory: Path) -> bool:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    slides = [directory / name for name in manifest["slides"]]
    return calculate_version_hash(slides, manifest["caption"], manifest["metadata"]) == manifest["content_hash"]

