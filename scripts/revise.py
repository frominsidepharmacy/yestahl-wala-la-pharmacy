#!/usr/bin/env python3
import argparse, json, os, shutil
from pathlib import Path
from src.approval import freeze_manifest
from src.design import render_carousel
from src.models import Product
from src.revision import apply_safe_revision

parser = argparse.ArgumentParser(); parser.add_argument("--publication-key", required=True); parser.add_argument("--pending-root", required=True)
args = parser.parse_args()
source = next(Path(args.pending_root).rglob("manifest.json")).parent
manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
content = json.loads((source / "content.json").read_text(encoding="utf-8"))
content, caption, edit = apply_safe_revision(content, manifest["caption"], os.environ["EDIT_INSTRUCTION"])
meta = manifest["metadata"]; meta["version"] = int(meta.get("version", 1)) + 1
raw = dict(meta["product"]); raw.pop("product_id", None); product = Product(**raw)
target = Path("output/revised") / args.publication_key
slides = render_carousel(product, content, target)
freeze_manifest(target, slides, caption, meta)
(target / "content.json").write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
(target / "edit.json").write_text(json.dumps(edit, ensure_ascii=False, indent=2), encoding="utf-8")

