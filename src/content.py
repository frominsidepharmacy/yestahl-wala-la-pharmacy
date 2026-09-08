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
        "price": product.price_aed, "retailer": product.retailer,
        "use_case": ingredients[0]["uses"][0] if ingredients else None,
        "claim": ingredients[0]["uses"][0] if ingredients else None,
    }
    usable = [h for h in hooks if all(values.get(field) is not None for field in __import__("re").findall(r"{(\w+)}", h))]
    index = int(hashlib.sha256(product.normalized_id.encode()).hexdigest(), 16) % len(usable)
    return usable[index].format(**values)


def verdict(product: Product, score: float, ingredients: List[Dict]) -> Tuple[str, str]:
    if not ingredients:
        return "❌ مش أفضل اختيار", "المعلومات الموثقة عن التركيبة مش كفاية للحكم الإيجابي."
    if score >= 78:
        return "✅ يستاهل", "تركيبة مفهومة، استخدام واضح، ودليل مناسب للغرض المقصود."
    if score >= 62:
        return "🟡 يستاهل بشروط", "مفيد للشخص المناسب، لكن الاحتياج وطريقة الاستخدام أهم من شهرة المنتج."
    if score >= 48:
        return "🟠 كويس... بس فيه بدائل أقوى", "التركيبة مقبولة، لكن القيمة أو وضوح المعلومات مش الأفضل."
    return "❌ مش أفضل اختيار", "الدليل أو القيمة المتاحة حاليًا لا يبرران الاختيار."


def _available(value, suffix=""):
    return f"{value}{suffix}" if value is not None else "غير متاح"


def build_content(product: Product, ingredients: List[Dict], score: float) -> Dict:
    hook = choose_hook(product, ingredients)
    decision, reason = verdict(product, score, ingredients)
    uses = []
    for ingredient in ingredients:
        uses.extend(ingredient.get("uses", []))
    uses = list(dict.fromkeys(uses))[:4] or ["اللي محتاج معلومات أوضح قبل الشراء"]
    warning = ingredients[0]["warnings_ar"] if ingredients else "راجع مختص لو عندك حالة صحية أو بتستخدم أدوية."
    category_usage = {
        "korean_skincare": ["كمية صغيرة على بشرة نظيفة", "مرة يوميًا وابدأ تدريجيًا", "حسب نوع المنتج صباحًا أو مساءً", warning],
        "vitamins_supplements": ["التزم بالجرعة الرسمية على العبوة", "حسب الاحتياج وتوجيه المختص", "خده في توقيت ثابت مناسب للتعليمات", warning],
        "personal_care": ["استخدم كمية مناسبة على المنطقة المقصودة", "حسب تعليمات العبوة", "انتظم بدون إفراط", warning],
    }[product.category]
    slide3 = [{"title": x["display"], "body": x["explanation_ar"]} for x in ingredients[:4]]
    if not slide3:
        slide3 = [{"title": "المعلومات المتاحة", "body": "قائمة المكونات الرسمية غير كافية؛ وده مؤثر على الحكم."}]
    checked = datetime.now().strftime("%d/%m/%Y")
    return {
        "hook": hook, "verdict": decision, "verdict_reason": reason,
        "slides": [
            {"title": "يستاهل ولا لأ؟", "subtitle": product.product_name, "blocks": [hook]},
            {"title": "هو إيه أصلًا؟", "blocks": [f"الفئة: {product.category.replace('_', ' ')}", f"الهدف: {uses[0]}", f"الحجم: {_available(product.pack_size)}", f"المتاح حاليًا: {'أيوه' if product.availability is not False else 'لأ'}"]},
            {"title": "إيه جوه التركيبة؟", "blocks": [f"{x['title']} — {x['body']}" for x in slide3]},
            {"title": "مناسب لمين؟", "blocks": [f"• {x}" for x in uses] + ["مش أفضل اختيار لو المعلومات الرسمية مش كافية لهدفك."]},
            {"title": "استخدمه إزاي؟", "blocks": category_usage},
            {"title": "يستاهل ولا لأ؟", "blocks": [decision, reason, f"السعر: AED {_available(product.price_aed)}", f"العبوة: {_available(product.pack_size)}", f"المتجر: {product.retailer}", f"التقييم: {_available(product.rating)} | المراجعات: {_available(product.reviews_count)}", f"السعر وقت إعداد البوست: {checked}", "الأسعار والعروض ممكن تتغير.", "إيه المنتج اللي عايزني أحطه تحت الميكروسكوب المرة الجاية؟"]},
        ],
    }


def build_caption(product: Product, content: Dict, ingredients: List[Dict]) -> str:
    ingredient_text = "\n".join(f"• {i['display']}: {i['explanation_ar']}" for i in ingredients[:3]) or "• قائمة المكونات الرسمية المتاحة غير كافية للحكم التفصيلي."
    return f"""يستاهل ولا لأ؟ 🔍
من جوه الصيدلية، النهارده بنبص على {product.product_name}.

{content['hook']}

أهم اللي عرفناه عن التركيبة:
{ingredient_text}

الحكم: {content['verdict']}
{content['verdict_reason']}

السعر وقت المراجعة: AED {_available(product.price_aed)}
المتجر: {product.retailer}
تاريخ المراجعة: {datetime.now().strftime('%d/%m/%Y')}
الأسعار والعروض ممكن تتغير، والمحتوى للتثقيف ومش بديل عن نصيحة طبية شخصية.

إيه المنتج اللي عايزني أحطه تحت الميكروسكوب المرة الجاية؟

#يستاهل_ولا_لأ #من_جوه_الصيدلية #صيدلي #العناية_الشخصية"""
