#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from src.config import assert_guardrails
from src.publishing import prepare_approved_site


assert_guardrails()
key = os.environ["PUBLICATION_KEY"]
digest = os.environ["CONTENT_HASH"]
if not key.startswith("biz-"):
    raise SystemExit("Business staging refuses a non-business publication key")

matches = []
for manifest_path in Path("pending_business").rglob("manifest.json"):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    metadata = manifest.get("metadata", {})
    if metadata.get("account") == "business.by.dr_amrou" and metadata.get("publication_key") == key:
        matches.append(manifest_path.parent)
if len(matches) != 1:
    raise SystemExit(f"Expected one business pending version for {key}, found {len(matches)}")

approved = Path("approved_business") / key
approved.parent.mkdir(parents=True, exist_ok=True)
shutil.copytree(matches[0], approved, dirs_exist_ok=True)
prepare_approved_site(approved, Path("site"), key, digest)
(Path("site") / ".nojekyll").touch()
