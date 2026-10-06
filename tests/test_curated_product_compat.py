from src.models import Product


def test_curated_manifest_without_commerce_fields():
    data = {"product_id": "bojdeep30ml", "product_name": "Glow Deep Serum",
            "product_url": "https://example.com/product", "category": "korean_skincare",
            "pack_size": "30ml", "main_ingredient": "Alpha-Arbutin"}
    original = dict(data)
    product = Product.from_dict(data)
    assert product.brand is None
    assert product.retailer == ""
    assert product.pack_size == "30ml"
    assert data == original


def test_known_commerce_fields_are_preserved():
    product = Product.from_dict({"product_name": "Test", "product_url": "https://example.com",
                                 "category": "personal_care", "brand": "Brand", "retailer": "Store"})
    assert (product.brand, product.retailer) == ("Brand", "Store")
def test_curated_product_without_commerce_url():
    from src.models import Product
    data = {"product_name": "Aveeno Baby Wash", "category": "personal_care", "pack_size": "400 ml"}
    product = Product.from_dict(data)
    assert product.product_url == ""
    assert "product_url" not in data
    assert product.normalized_id
