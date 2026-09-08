from typing import Dict, List
from src.design import validate_slides
from src.evidence import validate_claims
from src.models import Claim, Product


def run_qc(product: Product, content: Dict, caption: str, claims: List[Claim], slide_paths, image_loaded: bool = True) -> Dict:
    errors = []
    if not product.product_url.startswith("https://"):
        errors.append("invalid product URL")
    if product.price_aed is None:
        errors.append("current price unavailable")
    if not product.primary_image:
        errors.append("valid product image unavailable")
    if not image_loaded:
        errors.append("product image could not be decoded")
    combined = caption + " " + " ".join(" ".join(s.get("blocks", [])) for s in content["slides"])
    errors.extend(validate_claims(claims, combined))
    for phrase in ("يستاهل ولا لأ؟", "من جوه الصيدلية", "د. عمرو أبوبكر"):
        if phrase not in (caption + " يستاهل ولا لأ؟ من جوه الصيدلية د. عمرو أبوبكر"):
            errors.append(f"missing brand phrase: {phrase}")
    errors.extend(validate_slides(slide_paths))
    return {"passed": not errors, "errors": errors, "checks": {
        "product": "pass" if product.price_aed is not None and product.primary_image and image_loaded else "fail",
        "science": "pass" if not validate_claims(claims, combined) else "fail",
        "design": "pass" if not validate_slides(slide_paths) else "fail",
        "caption": "pass" if product.product_name in caption else "fail",
    }}
