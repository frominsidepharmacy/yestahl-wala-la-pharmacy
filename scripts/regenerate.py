#!/usr/bin/env python3
import argparse, json
from pathlib import Path
from src.models import Product
from src.pipeline import prepare_product

parser = argparse.ArgumentParser(); parser.add_argument("--publication-key", required=True); parser.add_argument("--pending-root", required=True)
args = parser.parse_args()
source = next(Path(args.pending_root).rglob("manifest.json")).parent
raw = json.loads((source / "product.json").read_text(encoding="utf-8")); raw.pop("product_id", None)
prepare_product(Product(**raw), Path("output/regenerated") / args.publication_key, allow_recent=True)
