#!/usr/bin/env python3
import json, os
from pathlib import Path
from src.approval import verify_manifest
from src.config import ROOT, assert_guardrails
from src.publishing import prepare_approved_site

assert_guardrails()
key, digest = os.environ["PUBLICATION_KEY"], os.environ["CONTENT_HASH"]
matches = [p.parent for p in Path("pending").rglob("manifest.json") if json.loads(p.read_text(encoding="utf-8"))["metadata"].get("product") and key.endswith(json.loads(p.read_text(encoding="utf-8"))["metadata"]["product"]["product_id"][:8])]
if len(matches) != 1:
    raise SystemExit(f"Expected one pending version for {key}, found {len(matches)}")
approved = Path("approved") / key
approved.parent.mkdir(parents=True, exist_ok=True)
__import__("shutil").copytree(matches[0], approved, dirs_exist_ok=True)
manifest = json.loads((approved / "manifest.json").read_text(encoding="utf-8"))
prepare_approved_site(approved, Path("site"), key, manifest["content_hash"] if manifest["content_hash"].startswith(digest) else digest)
(Path("site") / ".nojekyll").touch()
