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
        "price": product.price_aed, "retailer": None,
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


def _product_kind(product: Product) -> str:
    if product.category == "korean_skincare":
        return "منتج عناية بالبشرة"
    if product.category == "vitamins_supplements":
        return "مكمل غذائي"
    return "منتج عناية شخصية"


def _usage_copy(product: Product, warning: str) -> List[str]:
    if product.category == "korean_skincare":
        return [
            "ابدأ بكمية صغيرة على بشرة نظيفة",
            "استخدمه مرة يوميًا في البداية",
            "لو بشرتك حساسة ابدأ يوم بعد يوم",
            "استخدم واقي شمس صباحًا",
        ]
    if product.category == "vitamins_supplements":
        return [
            "التزم بالجرعة المكتوبة على العبوة",
            "خده في ميعاد ثابت مناسب للتعليمات",
            "ما تزودش الجرعة من نفسك",
            "جرعة الأطفال يحددها العمر وتوجيه الطبيب أو الصيدلي",
        ]
    return [
        "استخدم كمية مناسبة على المكان المطلوب",
        "التزم بالطريقة المكتوبة على العبوة",
        "ما تكررش الاستخدام أكتر من الموصى به",
        "اغسل إيدك بعد الاستخدام لو المنتج موضعي",
    ]


def _warning_copy(product: Product, warning: str) -> List[str]:
    common = [warning]
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
    slide3 = [{"title": x["display"], "body": x["explanation_ar"]} for x in ingredients[:4]]
    if not slide3:
        slide3 = [{"title": "المعلومات المتاحة", "body": "قائمة المكونات الرسمية غير كافية؛ وده مؤثر على الحكم."}]
    checked = datetime.now().strftime("%d/%m/%Y")
    return {
        "hook": hook, "verdict": decision, "verdict_reason": reason,
        "slides": [
            {"title": "٥ حاجات لازم تعرفهم", "subtitle": product.product_name, "blocks": [
                f"استخدامه: {uses[0]}",
                f"أبرز مكوّن: {ingredients[0]['display'] if ingredients else 'غير موضح بالكامل'}",
                f"أهم تحذير: {warning}",
                f"السعر: {_available(product.price_aed)} درهم | الحجم: {_available(product.pack_size)}",
            ]},
            {"title": f"هو إيه {product.brand or _short_product_name(product)}؟", "blocks": [
                f"{product.product_name}",
                _product_kind(product),
                f"أبرز مكوّن موثق: {ingredients[0]['display'] if ingredients else 'المكونات غير موضحة بالكامل'}",
                f"حجم العبوة: {_available(product.pack_size)}",
            ]},
            {"title": "بيعمل إيه؟", "blocks": [f"{x['title']}: {x['body']}" for x in slide3]},
            {"title": "الطريقة الصح", "blocks": category_usage},
            {"title": "خد بالك", "blocks": cautions},
            {"title": "الخلاصة", "blocks": [
                decision,
                reason,
                f"السعر: {_available(product.price_aed)} درهم",
                f"الحجم: {_available(product.pack_size)}",
                f"التقييم: {_available(product.rating)} من 5",
                f"السعر اتراجع يوم {checked} وممكن يتغير",
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

السعر: {_available(product.price_aed)} درهم
الأسعار والعروض ممكن تتغير، والمحتوى للتثقيف ومش بديل عن نصيحة طبية شخصية.

إيه المنتج اللي عايزني أحطه تحت الميكروسكوب المرة الجاية؟

#يستاهل_ولا_لأ #من_جوه_الصيدلية #صيدلي {category_tags}"""
