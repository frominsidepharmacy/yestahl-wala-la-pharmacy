from typing import Dict, Tuple
from src.models import Product


def score_product(product: Product, researchable: bool = True, interesting_ingredients: int = 0,
                  audience_usefulness: float = 0.7, novelty: bool = True) -> Tuple[float, Dict[str, float]]:
    evidence = 25 if researchable else 0
    formula = min(20, 10 + interesting_ingredients * 4) if researchable and interesting_ingredients else 0
    usage = 15 if product.usage else 0
    safety = 10 if product.written_side_effects else (5 if researchable else 0)
    competitive = 10 if product.competitive_advantage and (product.competitive_advantage_source or "").startswith("https://") else 0
    value = 10 if (product.old_price_aed is not None or product.price_aed is not None) else 0
    availability = 3 if product.availability is not False else 0
    pack_clarity = 4 if product.pack_size else 0
    usefulness = min(3, max(0, audience_usefulness) * 3)
    breakdown = {"scientific_researchability": evidence, "active_formula": formula,
                 "written_usage": usage, "written_safety": safety,
                 "verified_competitive_advantage": competitive,
                 "original_price_value": value, "availability": availability,
                 "pack_clarity": pack_clarity, "audience_usefulness": round(usefulness, 2)}
    return round(sum(breakdown.values()), 2), breakdown
