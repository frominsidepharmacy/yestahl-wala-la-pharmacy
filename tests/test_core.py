import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from PIL import Image

from src.approval import calculate_version_hash, freeze_manifest, verify_manifest
from src.config import load_yaml
from src.content import build_caption, build_content, choose_hook, original_price, verdict
from src.design import _palette, render_carousel, validate_slides
from src.evidence import map_product_ingredients, validate_claims
from src.history import History
from src.models import Claim, Product
from src.qc import run_qc
from src.retailers import BinSinaAdapter, BootsAdapter, LifeAdapter
from src.retailers.base import parse_html_product, parse_jsonld_products, parse_pack, parse_price
from src.revision import apply_safe_revision, classify_edit
from src.scoring import score_product
from src.telegram import TelegramClient, authorized_user, callback_data, inline_keyboard, parse_callback


def product(**overrides):
    data = dict(product_name="COSRX Salicylic Cleanser 150ml", brand="COSRX", retailer="LIFE Pharmacy UAE",
                product_url="https://example.com/product", category="korean_skincare", price_aed=18.95,
                old_price_aed=72.45, discount_percentage=74, retailer_sku="135560", pack_size="150ml",
                volume_ml=150, rating=4.8, reviews_count=284, availability=True,
                primary_image="https://example.com/p.png", retailer_description="Contains salicylic acid")
    data.update(overrides)
    return Product(**data)


def test_category_palettes_are_distinct_and_product_color_is_micro_accent():
    config = load_yaml("design.yaml")
    package = Image.new("RGB", (30, 30), "#E71D36")
    palettes = {
        category: _palette(product(category=category), config, package)
        for category in ("korean_skincare", "personal_care", "vitamins_supplements")
    }
    assert len({palette["accent"] for palette in palettes.values()}) == 3
    assert len({palette["paper_blue"] for palette in palettes.values()}) == 3
    assert all(palette["product_accent"] == "#E71D36" for palette in palettes.values())
    assert config["product_color"]["max_visual_share_percent"] <= 15


@pytest.mark.parametrize("raw,expected", [("AED 19.50", 19.5), ("D 18.95", 18.95), ("1,299.00", 1299), (None, None)])
def test_parse_price(raw, expected): assert parse_price(raw) == expected


def test_parse_pack_all_units():
    assert parse_pack("100 ml 60 capsules 10 sachets 2 pcs") == {"volume_ml": 100, "tablet_count": None, "capsule_count": 60, "sachet_count": 10, "piece_count": 2}


def test_jsonld_parsing():
    html = (Path(__file__).parent / "fixtures/product.html").read_text()
    p = parse_jsonld_products(html, "LIFE", "korean_skincare", "https://example.com")[0]
    assert (p.price_aed, p.rating, p.reviews_count, p.volume_ml) == (18.95, 4.8, 284, 150)


def test_html_fallback():
    p = parse_html_product('<h1>Thing 50ml</h1><meta property="product:price:amount" content="23.5"><meta property="og:image" content="https://x/i.png">', "Boots", "personal_care", "https://x/p")
    assert p.price_aed == 23.5 and p.volume_ml == 50


def test_html_fallback_extracts_original_pre_offer_price():
    html = '''<h1>Thing 50ml</h1>
    <meta property="product:price:amount" content="23.5">
    <meta property="product:original_price:amount" content="47">
    <meta property="og:image" content="https://x/i.png">'''
    p = parse_html_product(html, "Boots", "personal_care", "https://x/p")
    assert p.price_aed == 23.5
    assert p.old_price_aed == 47
    assert p.discount_percentage == 50
    assert p.offer_flag


def test_public_price_prefers_verified_original_before_offer():
    p = product(price_aed=18.95, old_price_aed=72.45)
    ingredients, _ = map_product_ingredients(p)
    content = build_content(p, ingredients, 70)
    public_copy = json.dumps(content, ensure_ascii=False) + build_caption(p, content, ingredients)
    assert original_price(p) == 72.45
    assert "السعر الأصلي قبل العرض: 72.45 درهم" in public_copy
    assert "السعر: 18.95 درهم" not in public_copy


def test_best_offer_and_retailer_appear_in_caption_only():
    p = product(best_offer_price_aed=18.95, best_offer_retailer="LIFE Pharmacy UAE")
    ingredients, _ = map_product_ingredients(p)
    content = build_content(p, ingredients, 70)
    caption = build_caption(p, content, ingredients)
    assert "أفضل سعر عرض وجدناه وقت المراجعة: 18.95 درهم لدى LIFE Pharmacy UAE" in caption
    assert "LIFE Pharmacy UAE" not in json.dumps(content, ensure_ascii=False)


def test_written_usage_side_effects_and_sizes_are_used():
    p = product(
        usage="قرص واحد يوميًا بعد الأكل",
        written_side_effects=["قد يسبب اضطرابًا بسيطًا بالمعدة"],
        available_sizes=["30 قرص", "60 قرص"],
    )
    ingredients, _ = map_product_ingredients(p)
    content = build_content(p, ingredients, 70)
    assert content["slides"][3]["blocks"][0] == "قرص واحد يوميًا بعد الأكل"
    assert content["slides"][4]["blocks"][0] == "قد يسبب اضطرابًا بسيطًا بالمعدة"
    assert "30 قرص, 60 قرص" in content["slides"][1]["blocks"][3]


def test_pack_aware_normalization():
    assert product(pack_size="30 capsules", volume_ml=None, capsule_count=30).normalized_id != product(pack_size="60 capsules", volume_ml=None, capsule_count=60).normalized_id


def test_cross_retailer_same_pack_deduplicates():
    a = product(retailer="LIFE", retailer_sku=None, ean="123")
    b = product(retailer="Boots", retailer_sku="x", ean="123")
    assert a.normalized_id == b.normalized_id


def test_history_90_day_rule(tmp_path):
    h = History(tmp_path / "h.sqlite")
    p = product(); h.upsert("key", p, "PUBLISHED")
    assert h.used_recently(p.normalized_id, 90)


def test_history_old_record_allowed(tmp_path):
    h = History(tmp_path / "h.sqlite"); p = product(); h.upsert("key", p, "PUBLISHED")
    h.db.execute("UPDATE posts SET date=?", ((datetime.now(timezone.utc)-timedelta(days=91)).date().isoformat(),)); h.db.commit()
    assert not h.used_recently(p.normalized_id, 90)


def test_score_breakdown_totals():
    total, parts = score_product(product(), True, 2)
    assert total == round(sum(parts.values()), 2) and 0 <= total <= 100


def test_popularity_cannot_overcome_missing_evidence():
    total, parts = score_product(product(reviews_count=100000), False, 0, 0)
    assert parts["scientific_researchability"] == 0 and total < 50


def test_worthiness_score_rewards_decision_factors_not_popularity():
    strong = product(
        usage="قرص واحد يوميًا بعد الأكل",
        written_side_effects=["قد يسبب اضطرابًا بسيطًا بالمعدة"],
        competitive_advantage="تركيز المادة الفعالة موضح بوضوح",
        competitive_advantage_source="https://example.com/label",
    )
    weak = product(reviews_count=100000, rating=5, usage=None, written_side_effects=[])
    strong_score, strong_parts = score_product(strong, True, 2)
    weak_score, _ = score_product(weak, True, 2)
    assert strong_score > weak_score
    assert strong_parts["written_usage"] == 15
    assert strong_parts["verified_competitive_advantage"] == 10


def test_ingredient_mapping():
    ingredients, claims = map_product_ingredients(product())
    assert ingredients[0]["key"] == "salicylic_acid" and claims[0].source_url.startswith("https://")


def test_unsupported_claim_blocked():
    assert validate_claims([], "يعالج نهائي")


def test_unverified_concentration_blocked():
    assert "unverified concentration: 10%" in validate_claims([], "فيه 10%")


def test_hook_only_uses_available_variables():
    hook = choose_hook(product(reviews_count=None, rating=None, discount_percentage=None), [])
    assert "{" not in hook


def test_verdict_requires_evidence():
    assert verdict(product(), 99, [])[0].startswith("❌")


def test_caption_branding_and_product():
    p = product(); ingredients, _ = map_product_ingredients(p); content = build_content(p, ingredients, 70)
    cap = build_caption(p, content, ingredients)
    assert p.product_name in cap and "يستاهل ولا لأ؟" in cap and "من جوه الصيدلية" in cap
    assert "السعر وقت المراجعة" not in cap and "تاريخ المراجعة" not in cap


@pytest.mark.parametrize("category,tag", [
    ("korean_skincare", "#العناية_بالبشرة"),
    ("vitamins_supplements", "#فيتامينات"),
    ("personal_care", "#العناية_الشخصية"),
])
def test_caption_uses_category_specific_tags(category, tag):
    p = product(category=category)
    ingredients, _ = map_product_ingredients(p)
    assert tag in build_caption(p, build_content(p, ingredients, 70), ingredients)


def test_reference_story_structure_and_no_retailer_name():
    p = product(); ingredients, _ = map_product_ingredients(p); content = build_content(p, ingredients, 70)
    titles = [slide["title"] for slide in content["slides"]]
    assert titles[0] == "٥ حاجات لازم تعرفهم"
    assert titles[1:] == ["المادة الفعالة ودورها", "إيه اللي يميزه؟", "الطريقة الصح", "خد بالك", "الخلاصة"]
    public_copy = json.dumps(content, ensure_ascii=False) + build_caption(p, content, ingredients)
    assert p.retailer not in public_copy
    assert all(phrase not in public_copy for phrase in ("يختلف من شخص لآخر", "كل جسم", "كل بشرة مختلفة"))


def test_qc_rejects_sale_without_verified_original_price(tmp_path):
    p = product(old_price_aed=None, discount_percentage=20, offer_flag=True)
    ingredients, claims = map_product_ingredients(p)
    content = build_content(p, ingredients, 70)
    caption = build_caption(p, content, ingredients)
    report = run_qc(p, content, caption, claims, [], image_loaded=True)
    assert "original pre-offer price unavailable" in report["errors"]


def test_render_six_rtl_slides(tmp_path):
    p = product(primary_image=None); ingredients, _ = map_product_ingredients(p); content = build_content(p, ingredients, 70)
    paths = render_carousel(p, content, tmp_path, Image.new("RGBA", (400, 500), "white"))
    assert validate_slides(paths) == []
    assert all(Image.open(path).size == (1080, 1350) for path in paths)


def test_brand_config_exact():
    brand = load_yaml("settings.yaml")["brand"]
    assert brand == {"account": "dramrouaboubakr", "series_name_ar": "يستاهل ولا لأ؟", "brand_line_ar": "من جوه الصيدلية", "creator_name_ar": "د. عمرو أبوبكر", "full_series_name_ar": "يستاهل ولا لأ؟ | من جوه الصيدلية"}


def test_telegram_authorization():
    assert authorized_user({"callback_query": {"from": {"id": 42}}}, "42")
    assert not authorized_user({"message": {"from": {"id": 9}}}, "42")


def test_callback_round_trip():
    value = callback_data("approve", "260908-k-12345678", 2, "a"*64, "12345")
    assert len(value.encode()) <= 64 and parse_callback(value)["artifact_run_id"] == "12345"


def test_keyboard_contains_all_actions():
    raw = json.dumps(inline_keyboard("260908-k-12345678", 1, "b"*64, "9"))
    assert all(action in raw for action in ("approve", "edit", "regenerate", "reject"))


def test_publish_confirmation_contains_real_link_and_account(monkeypatch):
    client = TelegramClient(token="token", chat_id="42")
    sent = {}
    monkeypatch.setattr(client, "call", lambda method, **data: sent.update(method=method, **data))
    client.send_publish_confirmation("من جوة الصيدلية", "dramrouaboubakr", "https://instagram.com/p/abc")
    assert sent["method"] == "sendMessage"
    assert "@dramrouaboubakr" in sent["text"]
    assert "https://instagram.com/p/abc" in sent["text"]


@pytest.mark.parametrize("text,area", [("خلي الهوك أقوى", "content"), ("غير الكابشن بس", "caption"), ("كبر صورة المنتج", "design"), ("السعر ده راجعه", "data_accuracy"), ("خلي من جوه الصيدلية أوضح", "branding")])
def test_edit_classification(text, area): assert area in classify_edit(text)["areas"]


def test_minimal_revision():
    p = product(); ing, _ = map_product_ingredients(p); content = build_content(p, ing, 70)
    revised, _, edit = apply_safe_revision(content, "caption", "اختصر سلايد 3")
    assert len(revised["slides"][2]["blocks"]) <= 2 and edit["scope"] == "minimal"


def test_approval_hash_detects_mutation(tmp_path):
    paths = []
    for i in range(6):
        path = tmp_path / f"slide{i:02}.png"; path.write_bytes(f"{i}".encode()); paths.append(path)
    freeze_manifest(tmp_path, paths, "caption", {"x": 1})
    assert verify_manifest(tmp_path)
    paths[0].write_bytes(b"changed")
    assert not verify_manifest(tmp_path)


def test_retailer_adapters_are_separate():
    assert {LifeAdapter.key, BootsAdapter.key, BinSinaAdapter.key} == {"life", "boots", "binsina"}


def test_dry_run_sources_have_complete_verified_fallbacks():
    sources = load_yaml("dry_run_sources.yaml")["sources"]
    assert set(sources) == {"korean_skincare", "vitamins_supplements", "personal_care"}
    for category, source in sources.items():
        fallback = source["fallback_product"]
        candidate = Product(product_url=source["url"], category=category, **fallback)
        assert candidate.product_name and candidate.retailer and candidate.price_aed
        assert candidate.primary_image.startswith("https://")
