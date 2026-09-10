from __future__ import annotations
from datetime import datetime
import hashlib
from typing import Dict, List, Tuple
from src.config import load_yaml
from src.models import Product


def choose_hook(product: Product, ingredients: List[Dict]) -> str:
    hooks = load_yaml("hooks.yaml")["hooks"]
    values = {
        "reviews": product.reviews_count, "rating": product.rating,
        "discount": round(product.discount_percentage or 0),
        "ingredient": ingredients[0]["display"] if ingredients else None,
        "price": original_price(product), "retailer": None,
        "use_case": ingredients[0]["uses"][0] if ingredients else None,
        "claim": ingredients[0]["uses"][0] if ingredients else None,
    }
    usable = [h for h in hooks if all(values.get(field) is not None for field in __import__("re").findall(r"{(\w+)}", h))]
    index = int(hashlib.sha256(product.normalized_id.encode()).hexdigest(), 16) % len(usable)
    return usable[index].format(**values)


def verdict(product: Product, score: float, ingredients: List[Dict]) -> Tuple[str, str]:
    if not ingredients:
        return "❌ مش أفضل اختيار", "المعلومات الموثقة عن التركيبة مش كفاية للحكم الإيجابي."
    active = ingredients[0]["display"]
    if score >= 78:
        advantage = product.competitive_advantage or ingredients[0].get("competitive_edge_ar")
        reason = f"يستاهل لأن {active} له دور واضح، وطريقة الاستخدام والقيمة مقابل السعر الأصلي مقنعين."
        if advantage:
            reason += f" ونقطة تميزه: {advantage}"
        return "✅ يستاهل", reason
    if score >= 62:
        missing = []
        if not product.usage:
            missing.append("تعليمات الاستخدام المكتوبة غير مكتملة")
        if not product.written_side_effects:
            missing.append("الآثار الجانبية المكتوبة غير موضحة")
        if not (product.competitive_advantage or ingredients[0].get("competitive_edge_ar")):
            missing.append("لا توجد ميزة تنافسية موثقة")
        detail = "، و".join(missing) or "السعر أو تفاصيل العبوة يحتاجوا مقارنة أدق"
        return "🟡 يستاهل بشروط واضحة", f"{active} له دور مفهوم، لكن {detail}."
    if score >= 48:
        return "🟠 لا يستاهل بالسعر ده", f"وجود {active} نقطة جيدة، لكن الدليل المتاح أو وضوح الاستخدام والقيمة لا يبرروا السعر الأصلي."
    return "❌ لا يستاهل", "المعلومات الموثقة لا تكفي لإثبات قيمة حقيقية مقابل السعر الأصلي."


def _available(value, suffix=""):
    return f"{value}{suffix}" if value is not None else "غير متاح"


def original_price(product: Product):
    """Return the verified pre-offer price when the page exposes one."""
    return product.old_price_aed if product.old_price_aed is not None else product.price_aed


def _price_copy(product: Product) -> str:
    label = "السعر الأصلي قبل العرض" if product.old_price_aed is not None else "السعر الأصلي المؤكد"
    return f"{label}: {_available(original_price(product))} درهم"


def _offer_caption_copy(product: Product) -> str:
    if product.best_offer_price_aed is not None and product.best_offer_retailer:
        return (
            f"أفضل سعر عرض وجدناه وقت المراجعة: {product.best_offer_price_aed} درهم "
            f"لدى {product.best_offer_retailer}\n{_price_copy(product)}"
        )
    return _price_copy(product)


def _product_kind(product: Product) -> str:
    if product.category == "korean_skincare":
        return "منتج عناية بالبشرة"
    if product.category == "vitamins_supplements":
        return "مكمل غذائي"
    return "منتج عناية شخصية"


def _usage_copy(product: Product, warning: str) -> List[str]:
    written = [product.usage.strip()] if product.usage and product.usage.strip() else []
    if product.category == "korean_skincare":
        return (written + [
            "ابدأ بكمية صغيرة على بشرة نظيفة",
            "استخدمه مرة يوميًا في البداية",
            "لو بشرتك حساسة ابدأ يوم بعد يوم",
            "استخدم واقي شمس صباحًا",
        ])[:4]
    if product.category == "vitamins_supplements":
        return (written + [
            "التزم بالجرعة المكتوبة على العبوة",
            "خده في ميعاد ثابت مناسب للتعليمات",
            "ما تزودش الجرعة من نفسك",
            "جرعة الأطفال يحددها العمر وتوجيه الطبيب أو الصيدلي",
        ])[:4]
    return (written + [
        "استخدم كمية مناسبة على المكان المطلوب",
        "التزم بالطريقة المكتوبة على العبوة",
        "ما تكررش الاستخدام أكتر من الموصى به",
        "اغسل إيدك بعد الاستخدام لو المنتج موضعي",
    ])[:4]


def _warning_copy(product: Product, warning: str) -> List[str]:
    common = list(product.written_side_effects) + [warning]
    if product.category == "korean_skincare":
        common += [
            "وقفه لو ظهر تهيج شديد أو حرقان مستمر",
            "ما تجمعش مواد فعالة قوية مرة واحدة من غير خطة واضحة",
            "ابعده عن العين والجروح",
        ]
    elif product.category == "vitamins_supplements":
        common += [
            "ما تزودش الجرعة لأن الزيادة مش معناها نتيجة أسرع",
            "اسأل مختص لو بتاخد أدوية أو عندك مرض مزمن",
            "احفظه بعيدًا عن متناول الأطفال",
        ]
    else:
        common += [
            "وقف الاستخدام لو حصل تهيج واضح",
            "ابعده عن العين والجروح إلا لو العبوة بتقول غير كده",
            "للاستعمال الخارجي فقط لو ده مذكور على العبوة",
        ]
    return common[:4]


def _short_product_name(product: Product) -> str:
    words = product.product_name.split()
    without_size = [word for word in words if not any(char.isdigit() for char in word)]
    return " ".join((without_size or words)[:4])


def build_content(product: Product, ingredients: List[Dict], score: float) -> Dict:
    decision, reason = verdict(product, score, ingredients)
    uses = []
    for ingredient in ingredients:
        uses.extend(ingredient.get("uses", []))
    uses = list(dict.fromkeys(uses))[:4] or ["اللي محتاج معلومات أوضح قبل الشراء"]
    warning = ingredients[0]["warnings_ar"] if ingredients else "راجع مختص لو عندك حالة صحية أو بتستخدم أدوية."
    hook = f"{product.product_name}: أبرز استخدام موثق هو {uses[0]}."
    category_usage = _usage_copy(product, warning)
    cautions = _warning_copy(product, warning)
    primary = ingredients[0] if ingredients else None
    competitive_edge = product.competitive_advantage or (primary.get("competitive_edge_ar") if primary else None)
    sizes = list(dict.fromkeys(product.available_sizes or ([product.pack_size] if product.pack_size else [])))
    slide3 = [{"title": x["display"], "body": x["explanation_ar"]} for x in ingredients[:4]]
    if not slide3:
        slide3 = [{"title": "المعلومات المتاحة", "body": "قائمة المكونات الرسمية غير كافية؛ وده مؤثر على الحكم."}]
    checked = datetime.now().strftime("%d/%m/%Y")
    return {
        "hook": hook, "verdict": decision, "verdict_reason": reason,
        "slides": [
            {"title": "٥ حاجات لازم تعرفهم", "subtitle": product.product_name, "blocks": [
                f"استخدامه: {uses[0]}",
                f"المادة الفعالة الأساسية: {primary['display'] if primary else 'غير موضحة بالكامل'}",
                f"أهم تحذير: {warning}",
                f"{_price_copy(product)} | الحجم: {_available(product.pack_size)}",
            ]},
            {"title": "المادة الفعالة ودورها", "blocks": [
                f"{product.product_name}",
                f"المادة الأساسية: {primary['display'] if primary else 'المكونات غير موضحة بالكامل'}",
                f"دورها: {primary['explanation_ar'] if primary else 'المصدر الرسمي لا يوضح مادة أساسية يمكن تقييمها.'}",
                f"الأحجام المتاحة: {', '.join(sizes) if sizes else 'لم تُذكر أحجام أخرى في المصدر'}",
            ]},
            {"title": "إيه اللي يميزه؟", "blocks": (
                ([f"ميزة تنافسية موثقة: {competitive_edge}"] if competitive_edge else [])
                + [f"{x['title']}: {x['body']}" for x in slide3]
            )[:4]},
            {"title": "الطريقة الصح", "blocks": category_usage},
            {"title": "خد بالك", "blocks": cautions},
            {"title": "الخلاصة", "blocks": [
                decision,
                reason,
                _price_copy(product),
                f"الحجم: {_available(product.pack_size)}",
                f"التقييم: {_available(product.rating)} من 5",
                f"تم تأكيد السعر من صفحة المنتج يوم {checked}",
            ]},
        ],
    }


def build_caption(product: Product, content: Dict, ingredients: List[Dict]) -> str:
    ingredient_text = "\n".join(f"• {i['display']}: {i['explanation_ar']}" for i in ingredients[:3]) or "• قائمة المكونات الرسمية المتاحة غير كافية للحكم التفصيلي."
    category_tags = {
        "korean_skincare": "#العناية_بالبشرة #سكين_كير",
        "vitamins_supplements": "#فيتامينات #مكملات_غذائية",
        "personal_care": "#العناية_الشخصية #برودكت_ريفيو",
    }[product.category]
    return f"""يستاهل ولا لأ؟ 🔍
من جوه الصيدلية، النهارده بنبص على {product.product_name}.

{content['hook']}

أهم اللي عرفناه عن التركيبة:
{ingredient_text}

الحكم: {content['verdict']}
{content['verdict_reason']}

{_offer_caption_copy(product)}
المادة الفعالة ودورها متراجعين من المصدر المذكور في ملف التحقق.

إيه المنتج اللي عايزني أحطه تحت الميكروسكوب المرة الجاية؟

#يستاهل_ولا_لأ #من_جوه_الصيدلية #صيدلي {category_tags}"""
