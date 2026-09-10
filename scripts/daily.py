#!/usr/bin/env python3
from __future__ import annotations
import json, os, hashlib
from pathlib import Path
from src.config import ROOT, assert_guardrails, load_yaml
from src.category_rotation import query_for_day
from src.content import original_price
from src.evidence import map_product_ingredients
from src.history import History
from src.models import Product
from src.pipeline import ADAPTERS, prepare_product
from src.scoring import score_product
from src.telegram import TelegramClient, inline_keyboard


def main():
    assert_guardrails()
    categories = load_yaml("categories.yaml")["categories"]
    target_category = os.getenv("TARGET_CATEGORY", "all")
    if target_category != "all" and target_category not in categories:
        raise ValueError(f"Unsupported TARGET_CATEGORY: {target_category}")
    selected_categories = categories if target_category == "all" else {target_category: categories[target_category]}
    fallback_sources = load_yaml("dry_run_sources.yaml")["sources"]
    history = History()
    summary, request_count = {}, 0
    if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
        count = len(selected_categories)
        TelegramClient().call("sendMessage", chat_id=os.getenv("TELEGRAM_CHAT_ID"),
            text=f"جهزت {count} منتج للمراجعة قبل النشر:\n\nيستاهل ولا لأ؟\nمن جوه الصيدلية")
    for category, config in selected_categories.items():
        discovery_query = query_for_day(config["queries"])
        candidates = []
        failures = []
        for retailer, cls in ADAPTERS.items():
            adapter = cls()
            try:
                candidates.extend(adapter.discover(discovery_query, category))
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
        same_product = [p for _, p in filtered if p.normalized_id == selected.normalized_id and p.price_aed is not None]
        if same_product:
            best_offer = min(same_product, key=lambda p: p.price_aed)
            if best_offer.old_price_aed is not None and best_offer.price_aed < best_offer.old_price_aed:
                selected.best_offer_price_aed = best_offer.price_aed
                selected.best_offer_retailer = best_offer.retailer
                selected.offer_flag = True
                selected.old_price_aed = best_offer.old_price_aed
                selected.discount_percentage = best_offer.discount_percentage
        result = prepare_product(selected, ROOT / "output" / "daily" / category, history)
        summary[category] = {"status": "PENDING_APPROVAL", "name": selected.product_name,
                             "discovery_query": discovery_query,
                             "publication_key": result["publication_key"], "content_hash": result["content_hash"]}
        if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
            manifest = json.loads((ROOT / "output" / "daily" / category / "manifest.json").read_text(encoding="utf-8"))
            p = selected
            control = f"""━━━━━━━━━━
🔬 يستاهل ولا لأ؟
من جوه الصيدلية

CATEGORY: {config['label']}
PRODUCT: {p.product_name}
ORIGINAL PRICE: AED {original_price(p) if original_price(p) is not None else 'غير متاح'}
BEST OFFER: {f'AED {p.best_offer_price_aed} at {p.best_offer_retailer}' if p.best_offer_price_aed is not None else 'لا يوجد عرض موثق'}
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
    approved_items = [v for v in summary.values() if v.get("content_hash")]
    if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID") and len(approved_items) > 1:
        run_id = os.getenv("GITHUB_RUN_ID", "0")
        combined = hashlib.sha256("".join(sorted(v["content_hash"] for v in approved_items)).encode()).hexdigest()[:12]
        TelegramClient().call("sendMessage", chat_id=os.getenv("TELEGRAM_CHAT_ID"),
            text="راجع النسخ الثلاثة، أو وافق عليهم كلهم:",
            reply_markup={"inline_keyboard": [[{"text": "✅ APPROVE ALL", "callback_data": f"approve_all:{combined}:{run_id}"}]]})
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
