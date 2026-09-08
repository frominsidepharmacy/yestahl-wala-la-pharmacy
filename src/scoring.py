from typing import Dict, Tuple
from src.models import Product


def score_product(product: Product, researchable: bool = True, interesting_ingredients: int = 0,
                  audience_usefulness: float = 0.7, novelty: bool = True) -> Tuple[float, Dict[str, float]]:
    reviews = min(15, ((product.reviews_count or 0) ** 0.5) * 0.75)
    rating = min(10, max(0, ((product.rating or 0) - 2.5) / 2.5 * 10))
    discount = min(10, max(0, product.discount_percentage or 0) / 5)
    formula = min(15, interesting_ingredients * 4)
    evidence = 20 if researchable else 0
    usefulness = min(15, max(0, audience_usefulness) * 15)
    value = 2.5 if product.price_aed is not None else 0
    availability = 5 if product.availability is not False else 0
    novel = 5 if novelty else 0
    breakdown = {"popularity_reviews": round(reviews, 2), "rating": round(rating, 2),
                 "discount": round(discount, 2), "interesting_formulation": formula,
                 "scientific_researchability": evidence, "audience_usefulness": round(usefulness, 2),
                 "price_value": value, "availability": availability, "novelty": novel}
    return round(sum(breakdown.values()), 2), breakdown

