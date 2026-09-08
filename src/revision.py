from __future__ import annotations
from typing import Dict


def classify_edit(instruction: str) -> Dict:
    text = instruction.strip().lower()
    areas = []
    mapping = {
        "caption": ["كابشن", "caption"], "branding": ["براند", "الصيدلية", "شعار"],
        "design": ["كبر", "صورة", "لون", "سلايد", "design"],
        "data_accuracy": ["سعر", "راجع", "دقة", "معلومة"],
        "content": ["هوك", "اختصر", "الحكم", "حدة", "محتوى"],
    }
    for area, terms in mapping.items():
        if any(term in text for term in terms):
            areas.append(area)
    return {"instruction": instruction, "areas": areas or ["content"], "scope": "caption_only" if "كابشن بس" in text else "minimal"}


def apply_safe_revision(content: Dict, caption: str, instruction: str):
    edit = classify_edit(instruction)
    if "هوك" in instruction and "أقوى" in instruction:
        content["hook"] = "المنتج ده مشهور جدًا... لكن في تفصيلة في التركيبة ممكن تغيّر قرارك."
        content["slides"][0]["blocks"] = [content["hook"]]
    if "الحكم" in instruction and "أقل حدة" in instruction and content["verdict"].startswith("❌"):
        content["verdict"] = "🟠 كويس... بس فيه بدائل أقوى"
        content["slides"][5]["blocks"][0] = content["verdict"]
    if "كابشن بس" not in instruction and "اختصر سلايد 3" in instruction:
        content["slides"][2]["blocks"] = content["slides"][2]["blocks"][:2]
    if "كابشن" in instruction and "اختصر" in instruction:
        caption = "\n".join(caption.splitlines()[:12])
    return content, caption, edit

