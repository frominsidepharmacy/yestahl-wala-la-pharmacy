from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Dict, Optional
from src.approval import freeze_manifest
from src.config import ROOT, assert_guardrails, load_yaml
from src.content import build_caption, build_content
from src.design import load_product_image, render_carousel
from src.evidence import evidence_bundle, map_product_ingredients
from src.history import History
from src.models import Product
from src.qc import run_qc
from src.retailers import BinSinaAdapter, BootsAdapter, LifeAdapter
from src.scoring import score_product


ADAPTERS = {"life": LifeAdapter, "boots": BootsAdapter, "binsina": BinSinaAdapter}


def prepare_product(product: Product, output_dir: Path, history: Optional[History] = None, allow_recent=False) -> Dict:
    assert_guardrails()
    history = history or History()
    if not allow_recent and history.used_recently(product.normalized_id, 90):
        raise RuntimeError("90-day no-repeat rule blocked product")
    ingredients, claims = map_product_ingredients(product)
    score, score_breakdown = score_product(product, bool(claims), len(ingredients))
    content = build_content(product, ingredients, score)
    caption = build_caption(product, content, ingredients)
    product_image = load_product_image(product.primary_image)
    slide_paths = render_carousel(product, content, output_dir, product_image)
    bundle = evidence_bundle(product, ingredients, claims)
    metadata = {"brand": load_yaml("settings.yaml")["brand"], "product": product.to_dict(),
                "score": score, "score_breakdown": score_breakdown, "verdict": content["verdict"], "version": 1}
    manifest = freeze_manifest(output_dir, slide_paths, caption, metadata)
    qc = run_qc(product, content, caption, claims, slide_paths, product_image is not None)
    for name, value in (("product.json", product.to_dict()), ("evidence_bundle.json", bundle),
                        ("score.json", {"score": score, "breakdown": score_breakdown}),
                        ("content.json", content), ("qc_report.json", qc)):
        (output_dir / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "caption.txt").write_text(caption, encoding="utf-8")
    code = {"korean_skincare": "k", "vitamins_supplements": "v", "personal_care": "p"}[product.category]
    publication_key = f"{datetime.now(timezone.utc).strftime('%y%m%d')}-{code}-{product.normalized_id[:8]}"
    history.upsert(publication_key, product, "PENDING_APPROVAL", score=score, verdict=content["verdict"], content_hash=manifest["content_hash"])
    return {"product": product, "score": score, "verdict": content["verdict"], "qc": qc,
            "publication_key": publication_key, "content_hash": manifest["content_hash"], "slides": slide_paths}


def live_dry_run(output_root: Optional[Path] = None) -> Dict:
    assert_guardrails()
    output_root = output_root or ROOT / "output" / "dry-run"
    sources = load_yaml("dry_run_sources.yaml")["sources"]
    results = {}
    history = History(output_root / "dry-run.sqlite3")
    for category, source in sources.items():
        adapter = ADAPTERS[source["retailer"]]()
        product = adapter.product(source["url"], category)
        result = prepare_product(product, output_root / category, history, allow_recent=True)
        results[category] = {"name": product.product_name, "retailer": product.retailer,
                             "price_aed": product.price_aed, "score": result["score"],
                             "verdict": result["verdict"], "qc_passed": result["qc"]["passed"]}
    (output_root / "summary.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return results
