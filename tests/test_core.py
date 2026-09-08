import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from PIL import Image

from src.approval import calculate_version_hash, freeze_manifest, verify_manifest
from src.config import load_yaml
from src.content import build_caption, build_content, choose_hook, verdict
from src.design import render_carousel, validate_slides
from src.evidence import map_product_ingredients, validate_claims
from src.history import History
from src.models import Claim, Product
from src.qc import run_qc
from src.retailers import BinSinaAdapter, BootsAdapter, LifeAdapter
from src.retailers.base import parse_html_product, parse_jsonld_products, parse_pack, parse_price
from src.revision import apply_safe_revision, classify_edit
from src.scoring import score_product
from src.telegram import authorized_user, callback_data, inline_keyboard, parse_callback


def product(**overrides):
    data = dict(product_name="COSRX Salicylic Cleanser 150ml", brand="COSRX", retailer="LIFE Pharmacy UAE",
                product_url="https://example.com/product", category="korean_skincare", price_aed=18.95,
                old_price_aed=72.45, discount_percentage=74, retailer_sku="135560", pack_size="150ml",
                volume_ml=150, rating=4.8, reviews_count=284, availability=True,
                primary_image="https://example.com/p.png", retailer_description="Contains salicylic acid")
    data.update(overrides)
    return Product(**data)


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


def test_reference_story_structure_and_no_retailer_name():
    p = product(); ingredients, _ = map_product_ingredients(p); content = build_content(p, ingredients, 70)
    titles = [slide["title"] for slide in content["slides"]]
    assert titles[0] == "٥ حاجات لازم تعرفهم"
    assert titles[2:] == ["بيعمل إيه؟", "الطريقة الصح", "خد بالك", "الخلاصة"]
    public_copy = json.dumps(content, ensure_ascii=False) + build_caption(p, content, ingredients)
    assert p.retailer not in public_copy


def test_render_six_rtl_slides(tmp_path):
    p = product(primary_image=None); ingredients, _ = map_product_ingredients(p); content = build_content(p, ingredients, 70)
    paths = render_carousel(p, content, tmp_path, Image.new("RGBA", (400, 500), "white"))
    assert validate_slides(paths) == []
    assert all(Image.open(path).size == (1080, 1350) for path in paths)


def test_brand_config_exact():
    brand = load_yaml("settings.yaml")["brand"]
    assert brand == {"series_name_ar": "يستاهل ولا لأ؟", "brand_line_ar": "من جوه الصيدلية", "creator_name_ar": "د. عمرو أبوبكر", "full_series_name_ar": "يستاهل ولا لأ؟ | من جوه الصيدلية"}


def test_telegram_authorization():
    assert authorized_user({"callback_query": {"from": {"id": 42}}}, "42")
    assert not authorized_user({"message": {"from": {"id": 9}}}, "42")


def test_callback_round_trip():
    value = callback_data("approve", "260908-k-12345678", 2, "a"*64, "12345")
    assert len(value.encode()) <= 64 and parse_callback(value)["artifact_run_id"] == "12345"


def test_keyboard_contains_all_actions():
    raw = json.dumps(inline_keyboard("260908-k-12345678", 1, "b"*64, "9"))
    assert all(action in raw for action in ("approve", "edit", "regenerate", "reject"))


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
