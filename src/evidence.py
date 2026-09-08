from __future__ import annotations
from datetime import datetime, timezone
import re
from typing import Dict, List, Tuple
from src.config import load_yaml
from src.models import Claim, Product


def normalize_ingredient(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


ALIASES = {
    "hyaluronic_acid": ["hyaluronic acid", "sodium hyaluronate"],
    "niacinamide": ["niacinamide", "nicotinamide"],
    "salicylic_acid": ["salicylic acid", "bha"],
    "ceramides": ["ceramide", "ceramides"],
    "panthenol": ["panthenol", "provitamin b5"],
    "retinol": ["retinol"],
    "vitamin_c": ["vitamin c", "ascorbic acid", "ascorbyl"],
    "vitamin_d": ["vitamin d", "cholecalciferol", "ergocalciferol"],
    "magnesium": ["magnesium"], "omega_3": ["omega-3", "omega 3", "epa", "dha"],
    "zinc": ["zinc"],
    "aloe_vera": ["aloe vera", "aloe barbadensis"],
}


def map_product_ingredients(product: Product) -> Tuple[List[Dict], List[Claim]]:
    library = load_yaml("ingredient_claims.yaml")["ingredients"]
    haystack = " ".join(product.ingredients + [product.product_name, product.retailer_description or ""]).lower()
    matches, claims = [], []
    now = datetime.now(timezone.utc).isoformat()
    for key, aliases in ALIASES.items():
        if key not in library or not any(alias in haystack for alias in aliases):
            continue
        item = dict(library[key])
        item["key"] = key
        matches.append(item)
        claims.append(Claim(f"ingredient-{key}", item["explanation_ar"], item["source"], "authoritative", 3, now))
    return matches[:4], claims[:4]


def validate_claims(claims: List[Claim], text: str) -> List[str]:
    errors = []
    forbidden = ["يعالج نهائي", "يشفي", "نتائج مضمونة", "بدون أي أعراض", "آمن 100%"]
    if any(term in text for term in forbidden):
        errors.append("unsupported absolute/treatment claim")
    for claim in claims:
        if not claim.source_url.startswith("https://") or claim.evidence_strength < 2:
            errors.append(f"weak evidence: {claim.claim_id}")
    concentration_claims = re.findall(r"\b\d+(?:\.\d+)?%", text)
    source_blob = " ".join(c.claim_text for c in claims)
    for concentration in concentration_claims:
        if concentration not in source_blob:
            errors.append(f"unverified concentration: {concentration}")
    return errors


def evidence_bundle(product: Product, ingredients: List[Dict], claims: List[Claim]) -> Dict:
    return {
        "product_id": product.normalized_id,
        "product_name": product.product_name,
        "retailer_source": {"url": product.product_url, "allowed_use": ["price", "pack", "availability", "image", "rating", "reviews"], "retrieved_at": product.retrieved_at},
        "ingredients": ingredients,
        "claims": [c.__dict__ for c in claims],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
