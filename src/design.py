from __future__ import annotations

from io import BytesIO
from pathlib import Path
import math
import random
from typing import Dict, List, Optional, Sequence, Tuple

import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps
import requests

from src.config import load_yaml
from src.models import Product


def _font(size: int, bold: bool = False):
    cfg = load_yaml("design.yaml")
    key = "font_bold_candidates" if bold else "font_candidates"
    for candidate in cfg.get(key, []) + cfg["font_candidates"]:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size, index=0)
    return ImageFont.load_default(size=size)


def _display(text: str) -> str:
    safe = str(text).replace("✅", "●").replace("🟡", "●").replace("🟠", "●").replace("❌", "×")
    return "\n".join(get_display(arabic_reshaper.reshape(line)) for line in safe.splitlines())


def _rtl(draw, xy, text, font, fill, anchor="ra", spacing=10):
    draw.multiline_text(xy, _display(text), font=font, fill=fill, anchor=anchor, align="right", spacing=spacing)


def _wrap(draw, text: str, font, max_width: int, max_lines: int = 4) -> str:
    words = str(text).split()
    lines, line = [], []
    for word in words:
        candidate = " ".join(line + [word])
        if draw.textbbox((0, 0), _display(candidate), font=font)[2] <= max_width:
            line.append(word)
        else:
            if line:
                lines.append(" ".join(line))
            line = [word]
            if len(lines) >= max_lines:
                break
    if line and len(lines) < max_lines:
        lines.append(" ".join(line))
    if len(lines) == max_lines and len(" ".join(lines).split()) < len(words):
        lines[-1] = lines[-1].rstrip(".…") + "…"
    return "\n".join(lines)


def _torn_points(box: Tuple[int, int, int, int], seed: int, step: int = 22, jitter: int = 7):
    x1, y1, x2, y2 = box
    rng = random.Random(seed)
    points = []
    points.extend((x, y1 + rng.randint(-jitter, jitter)) for x in range(x1, x2, step))
    points.extend((x2 + rng.randint(-jitter, jitter), y) for y in range(y1, y2, step))
    points.extend((x, y2 + rng.randint(-jitter, jitter)) for x in range(x2, x1, -step))
    points.extend((x1 + rng.randint(-jitter, jitter), y) for y in range(y2, y1, -step))
    return points


def _torn_box(draw, box, fill, seed, shadow=True, jitter=7):
    points = _torn_points(box, seed, jitter=jitter)
    if shadow:
        draw.polygon([(x + 7, y + 9) for x, y in points], fill="#D9D2C5")
    draw.polygon(points, fill=fill)


def _paper_texture(image: Image.Image, seed: int):
    rng = random.Random(seed)
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for _ in range(4200):
        x, y = rng.randrange(image.width), rng.randrange(image.height)
        color = rng.choice(((112, 91, 65, 13), (255, 255, 255, 24), (172, 151, 119, 10)))
        radius = rng.choice((1, 1, 1, 2))
        draw.ellipse((x, y, x + radius, y + radius), fill=color)
    image.paste(Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB"))


def _tape(draw, x: int, y: int, width: int = 92, height: int = 31):
    draw.polygon([(x, y + 5), (x + width, y), (x + width - 5, y + height), (x + 4, y + height - 3)], fill="#D9C49A")
    draw.line((x + 10, y + 7, x + width - 10, y + 3), fill="#C6AE7C", width=2)


def _palette(product: Product, base: Dict) -> Dict:
    palette = {
        "vitamins_supplements": {"accent": "#F6B51F", "accent2": "#FF7A00", "paper_blue": "#D9F0FF", "paper_alt": "#FAD9E2"},
        "korean_skincare": {"accent": "#087E78", "accent2": "#55C4C0", "paper_blue": "#D7EFEB", "paper_alt": "#EAF6F2"},
        "personal_care": {"accent": "#087E78", "accent2": "#55C4C0", "paper_blue": "#D7EFEB", "paper_alt": "#E9F4F1"},
    }[product.category]
    return {"navy": base["navy"], "off_white": "#F7F2E8", "paper": "#FFFDF7", "ink_blue": "#315C91", **palette}


def load_product_image(url: Optional[str]) -> Optional[Image.Image]:
    if not url:
        return None
    try:
        response = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        return Image.open(BytesIO(response.content)).convert("RGBA")
    except Exception:
        return None


def _paste_product(canvas: Image.Image, product_image: Optional[Image.Image], box, seed: int):
    if product_image is None:
        return
    x1, y1, x2, y2 = box
    card = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    _torn_box(ImageDraw.Draw(card), (x1 - 22, y1 - 22, x2 + 22, y2 + 22), "#FFFDF8", seed)
    canvas.paste(card, (0, 0), card)
    rgb = product_image.convert("RGB")
    difference = ImageChops.difference(rgb, Image.new("RGB", rgb.size, "white")).convert("L")
    bbox = difference.point(lambda value: 255 if value > 8 else 0).getbbox()
    if bbox:
        pad_x, pad_y = max(8, (bbox[2] - bbox[0]) // 12), max(8, (bbox[3] - bbox[1]) // 12)
        bbox = (max(0, bbox[0] - pad_x), max(0, bbox[1] - pad_y), min(rgb.width, bbox[2] + pad_x), min(rgb.height, bbox[3] + pad_y))
        product_image = product_image.crop(bbox)
    product = ImageOps.contain(product_image, (x2 - x1, y2 - y1))
    px, py = x1 + (x2 - x1 - product.width) // 2, y1 + (y2 - y1 - product.height) // 2
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((px + 9, py + 14, px + product.width + 9, py + product.height + 14), 20, fill=(38, 45, 51, 65))
    shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    canvas.paste(shadow, (0, 0), shadow)
    canvas.paste(product, (px, py), product)
    _tape(ImageDraw.Draw(canvas), x1 + (x2 - x1) // 2 - 45, y1 - 30)


def _brand_header(draw, colors, number: int, total: int):
    _torn_box(draw, (54, 42, 435, 159), colors["paper"], 700 + number)
    _rtl(draw, (403, 78), "من جوه", _font(28, True), colors["navy"], anchor="rs")
    _rtl(draw, (403, 122), "الصيدلية", _font(40, True), colors["navy"], anchor="rs")
    draw.rounded_rectangle((67, 68, 148, 135), 24, fill=colors["accent"])
    draw.arc((88, 89, 128, 121), 0, 180, fill="white", width=5)
    draw.line((91, 105, 125, 105), fill="white", width=5)
    _tape(draw, 322, 29, 100, 34)
    draw.ellipse((946, 40, 1040, 113), fill=colors["paper_blue"])
    draw.text((993, 76), f"{number}/{total}", font=_font(29, True), fill=colors["navy"], anchor="mm")
    draw.line((974, 132, 1030, 132), fill=colors["navy"], width=5)
    draw.line((1011, 116, 1031, 132, 1011, 148), fill=colors["navy"], width=5)


def _doodles(draw, colors, number: int):
    for offset in (0, 23, 46):
        draw.line((455 + offset, 252 - offset // 2, 427 + offset, 223 - offset // 2), fill=colors["accent2"], width=8)
    draw.arc((878, 92, 919, 137), 200, 520, fill=colors["ink_blue"], width=4)
    draw.arc((910, 92, 951, 137), 20, 340, fill=colors["ink_blue"], width=4)
    draw.line((884, 119, 916, 151, 946, 113), fill=colors["ink_blue"], width=4)
    draw.line((835, 163, 1014, 142), fill=colors["ink_blue"], width=3)
    if number % 2 == 0:
        draw.ellipse((23, 1120, 145, 1242), outline=colors["accent2"], width=6)
        for angle in range(0, 360, 45):
            x1, y1 = 84 + int(72 * math.cos(math.radians(angle))), 1181 + int(72 * math.sin(math.radians(angle)))
            x2, y2 = 84 + int(96 * math.cos(math.radians(angle))), 1181 + int(96 * math.sin(math.radians(angle)))
            draw.line((x1, y1, x2, y2), fill=colors["accent2"], width=5)


def _headline(draw, title: str, colors, number: int):
    _torn_box(draw, (455, 200, 1032, 365), colors["accent"], 900 + number, shadow=False)
    font = _font(54, True)
    wrapped = _wrap(draw, title, font, 515, 2)
    bbox = draw.multiline_textbbox((0, 0), _display(wrapped), font=font, spacing=8)
    _rtl(draw, (1002, 282 - (bbox[3] - bbox[1]) // 2), wrapped, font, "#FFFDF7", anchor="ra", spacing=8)


def _content_cards(draw, blocks: Sequence[str], colors, number: int):
    x1, x2, y1, bottom = 478, 1030, 395, 1195
    count = max(1, len(blocks))
    gap = 12 if count <= 6 else 7
    card_h = (bottom - y1 - gap * (count - 1)) // count
    font_size = 32 if count <= 5 else (27 if count <= 7 else 22)
    font = _font(font_size, True)
    for idx, block in enumerate(blocks):
        top = y1 + idx * (card_h + gap)
        fill = colors["paper_blue"] if idx % 3 == 0 else (colors["paper_alt"] if idx % 3 == 1 else colors["paper"])
        _torn_box(draw, (x1, top, x2, top + card_h), fill, number * 100 + idx, jitter=4)
        cy = top + card_h // 2
        draw.ellipse((x1 + 18, cy - 29, x1 + 76, cy + 29), fill="#C9EBE6")
        draw.text((x1 + 47, cy), str(idx + 1), font=_font(23, True), fill=colors["navy"], anchor="mm")
        wrapped = _wrap(draw, block, font, x2 - x1 - 120, 3 if count <= 6 else 2)
        bbox = draw.multiline_textbbox((0, 0), _display(wrapped), font=font, spacing=6)
        _rtl(draw, (x2 - 24, top + (card_h - (bbox[3] - bbox[1])) // 2), wrapped, font, colors["navy"], anchor="ra", spacing=6)


def _footer(draw, colors, number: int):
    _torn_box(draw, (475, 1214, 1028, 1307), colors["paper"], 1300 + number, shadow=False, jitter=4)
    _rtl(draw, (998, 1241), "د. عمرو أبوبكر", _font(28, True), colors["navy"], anchor="rs")
    _rtl(draw, (998, 1280), "20+ سنة خبرة في الصيدلة | EmpowerMinds", _font(20), colors["navy"], anchor="rs")
    draw.line((770, 1291, 998, 1291), fill=colors["accent2"], width=5)


def render_carousel(product: Product, content: Dict, output_dir: Path, image: Optional[Image.Image] = None) -> List[Path]:
    cfg = load_yaml("design.yaml")
    w, h = cfg["width"], cfg["height"]
    colors = _palette(product, cfg["colors"])
    output_dir.mkdir(parents=True, exist_ok=True)
    product_image = image or load_product_image(product.primary_image)
    paths = []
    total = len(content["slides"])
    for number, slide in enumerate(content["slides"], 1):
        canvas = Image.new("RGB", (w, h), colors["off_white"])
        _paper_texture(canvas, 20260 + number)
        draw = ImageDraw.Draw(canvas)
        _brand_header(draw, colors, number, total)
        _doodles(draw, colors, number)
        _headline(draw, slide["title"], colors, number)
        _paste_product(canvas, product_image, (65, 345, 430, 1035), 1100 + number)
        draw = ImageDraw.Draw(canvas)
        if number == 1:
            _torn_box(draw, (55, 1056, 440, 1174), colors["paper_blue"], 1220, jitter=5)
            subtitle = _wrap(draw, slide.get("subtitle", product.product_name), _font(28, True), 335, 3)
            _rtl(draw, (414, 1080), subtitle, _font(28, True), colors["navy"], anchor="ra", spacing=6)
        elif number == total:
            _torn_box(draw, (56, 1054, 441, 1173), colors["paper_blue"], 1280, jitter=5)
            _rtl(draw, (414, 1082), "اكتب: مقارنة\nللمنتج الجاي", _font(30, True), colors["navy"], anchor="ra")
        _content_cards(draw, list(slide.get("blocks", [])), colors, number)
        _footer(draw, colors, number)
        path = output_dir / f"slide{number:02d}.png"
        canvas.save(path, "PNG", optimize=True)
        paths.append(path)
    return paths


def validate_slides(paths: List[Path]) -> List[str]:
    errors = []
    if len(paths) != 6:
        errors.append("must contain exactly 6 slides")
    for number, path in enumerate(paths, 1):
        if not path.exists():
            errors.append(f"missing slide {number}")
            continue
        with Image.open(path) as image:
            if image.size != (1080, 1350) or image.format != "PNG":
                errors.append(f"slide {number} must be 1080x1350 PNG")
    return errors
