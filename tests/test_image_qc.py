from pathlib import Path
from PIL import Image
from src.content import build_caption, build_content
from src.evidence import map_product_ingredients
from src.models import Product
from src.qc import run_qc
from src.design import render_carousel


def test_undecodable_product_image_fails_qc(tmp_path):
    product = Product(product_name="Vitamin C 50ml", brand="X", retailer="Store", product_url="https://x/p",
                      category="personal_care", price_aed=10, pack_size="50ml", primary_image="https://x/missing.jpg")
    ingredients, claims = map_product_ingredients(product)
    content = build_content(product, ingredients, 60)
    caption = build_caption(product, content, ingredients)
    slides = render_carousel(product, content, tmp_path, Image.new("RGBA", (20, 20), "white"))
    qc = run_qc(product, content, caption, claims, slides, image_loaded=False)
    assert not qc["passed"] and "product image could not be decoded" in qc["errors"]
