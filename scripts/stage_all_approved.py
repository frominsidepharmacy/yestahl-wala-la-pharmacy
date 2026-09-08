#!/usr/bin/env python3
import hashlib, json, os, shutil
from pathlib import Path
from src.approval import verify_manifest
from src.publishing import prepare_approved_site

manifests = sorted(Path("pending").rglob("manifest.json"))
if not manifests:
    raise SystemExit("No manifests in pending artifact")
full_hashes = [json.loads(p.read_text(encoding="utf-8"))["content_hash"] for p in manifests]
combined = hashlib.sha256("".join(sorted(full_hashes)).encode()).hexdigest()
if not combined.startswith(os.environ["APPROVAL_HASH"]):
    raise SystemExit("Approval-all hash mismatch")
for path in manifests:
    source = path.parent
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not verify_manifest(source):
        raise SystemExit(f"Changed asset in {source}")
    product = manifest["metadata"]["product"]
    code = {"korean_skincare": "k", "vitamins_supplements": "v", "personal_care": "p"}[product["category"]]
    key = f"{__import__('datetime').datetime.now(__import__('datetime').timezone.utc).strftime('%y%m%d')}-{code}-{product['product_id'][:8]}"
    target = Path("approved") / key
    shutil.copytree(source, target, dirs_exist_ok=True)
    prepare_approved_site(target, Path("site"), key, manifest["content_hash"])
(Path("site") / ".nojekyll").touch()

