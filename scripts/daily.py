#!/usr/bin/env python3
from __future__ import annotations
import json, os, hashlib
from pathlib import Path
from src.config import ROOT, assert_guardrails, load_yaml
from src.evidence import map_product_ingredients
from src.history import History
from src.models import Product
from src.pipeline import ADAPTERS, prepare_product
from src.scoring import score_product
from src.telegram import TelegramClient, inline_keyboard


def main():
    assert_guardrails()
    categories = load_yaml("categories.yaml")["categories"]
    fallback_sources = load_yaml("dry_run_sources.yaml")["sources"]
    history = History()
    summary, request_count = {}, 0
    if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
        TelegramClient().call("sendMessage", chat_id=os.getenv("TELEGRAM_CHAT_ID"),
            text="صباح الخير 👋\n\nجهزت 3 منتجات جديدة لسلسلة:\n\nيستاهل ولا لأ؟\nمن جوه الصيدلية")
    for category, config in categories.items():
        candidates = []
        failures = []
        for retailer, cls in ADAPTERS.items():
            adapter = cls()
            try:
                candidates.extend(adapter.discover(config["queries"][0], category))
            except Exception as exc:
                failures.append(f"{retailer}: {exc}")
            request_count += adapter.requests_used
            if request_count >= 150:
                raise RuntimeError("MAX_RETAILER_PAGE_REQUESTS_PER_RUN reached; stopped safely")
        filtered = []
        for product in candidates:
            if history.used_recently(product.normalized_id, 90) or product.price_aed is None or not product.primary_image:
                continue
            if category == "korean_skincare" and not any(b.lower() in f"{product.brand} {product.product_name}".lower() for b in config["korean_brands"]):
                continue
            ingredients, claims = map_product_ingredients(product)
            if not claims:
                continue
            score, _ = score_product(product, True, len(ingredients))
            filtered.append((score, product))
        if not filtered:
            source = fallback_sources.get(category, {})
            fallback = source.get("fallback_product")
            if fallback:
                product = Product(
                    product_url=source["url"],
                    category=category,
                    **fallback,
                )
                ingredients, claims = map_product_ingredients(product)
                if claims:
                    score, _ = score_product(product, True, len(ingredients))
                    filtered.append((score, product))
                    failures.append("Live retailer discovery unavailable; used last-verified product snapshot.")
            if not filtered:
                summary[category] = {"status": "NO_VERIFIED_PRODUCT", "failures": failures,
                                     "message": "النهارده مفيش منتج يستحق النشر في الفئة دي بعد التحقق."}
                continue
        _, selected = max(filtered, key=lambda item: item[0])
        result = prepare_product(selected, ROOT / "output" / "daily" / category, history)
        summary[category] = {"status": "PENDING_APPROVAL", "name": selected.product_name,
                             "publication_key": result["publication_key"], "content_hash": result["content_hash"]}
        if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
            manifest = json.loads((ROOT / "output" / "daily" / category / "manifest.json").read_text(encoding="utf-8"))
            p = selected
            control = f"""━━━━━━━━━━
🔬 يستاهل ولا لأ؟
من جوه الصيدلية

CATEGORY: {config['label']}
PRODUCT: {p.product_name}
PRICE: AED {p.price_aed if p.price_aed is not None else 'غير متاح'}
SIZE: {p.pack_size or 'غير متاح'}
RATING: {p.rating if p.rating is not None else 'غير متاح'}
REVIEWS: {p.reviews_count if p.reviews_count is not None else 'غير متاح'}
VERDICT: {result['verdict']}
VERSION: v1

د. عمرو أبوبكر
━━━━━━━━━━"""
            TelegramClient().send_preview_files(result["slides"], control, manifest["caption"],
                inline_keyboard(result["publication_key"], 1, result["content_hash"], os.getenv("GITHUB_RUN_ID", "0")))
    daily_root = ROOT / "output" / "daily"
    daily_root.mkdir(parents=True, exist_ok=True)
    (daily_root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
        run_id = os.getenv("GITHUB_RUN_ID", "0")
        combined = hashlib.sha256("".join(sorted(v["content_hash"] for v in summary.values() if v.get("content_hash"))).encode()).hexdigest()[:12]
        TelegramClient().call("sendMessage", chat_id=os.getenv("TELEGRAM_CHAT_ID"),
            text="راجع النسخ الثلاثة، أو وافق عليهم كلهم:",
            reply_markup={"inline_keyboard": [[{"text": "✅ APPROVE ALL", "callback_data": f"approve_all:{combined}:{run_id}"}]]})
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
