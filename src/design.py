from __future__ import annotations
from io import BytesIO
from pathlib import Path
import re
from typing import Dict, List, Optional
import requests
import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont, ImageOps
from src.config import ROOT, load_yaml
from src.models import Product


def _font(size: int, bold: bool = False):
    cfg = load_yaml("design.yaml")
    for candidate in cfg["font_candidates"]:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size, index=0)
    return ImageFont.load_default(size=size)


def _display(text: str) -> str:
    safe = str(text).replace("✅", "●").replace("🟡", "●").replace("🟠", "●").replace("❌", "×")
    return "\n".join(get_display(arabic_reshaper.reshape(line)) for line in safe.splitlines())


def _rtl(draw, xy, text, font, fill, anchor="ra", spacing=12):
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


def load_product_image(url: Optional[str]) -> Optional[Image.Image]:
    if not url:
        return None
    try:
        response = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        return Image.open(BytesIO(response.content)).convert("RGBA")
    except Exception:
        return None


def render_carousel(product: Product, content: Dict, output_dir: Path, image: Optional[Image.Image] = None) -> List[Path]:
    cfg = load_yaml("design.yaml")
    w, h, margin = cfg["width"], cfg["height"], cfg["margin"]
    colors = cfg["colors"]
    output_dir.mkdir(parents=True, exist_ok=True)
    product_image = image or load_product_image(product.primary_image)
    paths = []
    for number, slide in enumerate(content["slides"], 1):
        canvas = Image.new("RGB", (w, h), colors["off_white"])
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle((margin, 42, w-margin, 154), 28, fill=colors["navy"])
        _rtl(draw, (w-margin-24, 88), "يستاهل ولا لأ؟", _font(42, True), "white", anchor="rm")
        _rtl(draw, (margin+24, 91), "من جوه الصيدلية", _font(25), colors["sky"], anchor="lm")
        y = 210
        _rtl(draw, (w-margin, y), _wrap(draw, slide["title"], _font(58, True), w-2*margin), _font(58, True), colors["navy"])
        y += 105
        if number == 1 and product_image is not None:
            boxed = ImageOps.contain(product_image, (520, 520))
            px = (w - boxed.width) // 2
            canvas.paste(boxed, (px, y), boxed)
            y += boxed.height + 35
            subtitle = slide.get("subtitle", "")
            _rtl(draw, (w-margin, y), _wrap(draw, subtitle, _font(40, True), w-2*margin, 2), _font(40, True), colors["navy"])
            y += 115
        elif number == 6:
            y += 20
        for idx, block in enumerate(slide.get("blocks", [])):
            size = 48 if (number == 6 and idx == 0) else (36 if number == 6 else 39)
            font = _font(size, idx == 0)
            max_lines = 2 if number == 6 else 3
            wrapped = _wrap(draw, block, font, w-2*margin-70, max_lines)
            bbox = draw.multiline_textbbox((0, 0), _display(wrapped), font=font, spacing=10)
            pad = 30 if number == 6 else 46
            block_h = bbox[3] - bbox[1] + pad
            if y + block_h > h - 125:
                raise ValueError(f"slide {number} content overflow at block {idx + 1}")
            fill = colors["sky"] if idx % 2 == 0 else "white"
            draw.rounded_rectangle((margin, y, w-margin, y+block_h), 22, fill=fill, outline="#D8E4EA")
            _rtl(draw, (w-margin-28, y+(14 if number == 6 else 22)), wrapped, font, colors["navy"])
            y += block_h + (10 if number == 6 else 18)
        draw.line((margin, h-92, w-margin, h-92), fill=colors["gold"], width=4)
        _rtl(draw, (w-margin, h-52), "د. عمرو أبوبكر", _font(27, True), colors["navy"], anchor="rs")
        draw.text((margin, h-66), f"{number}/6", font=_font(24), fill=colors["navy"])
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
