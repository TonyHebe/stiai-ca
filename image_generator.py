"""
image_generator.py
Generates styled Facebook post images in the "Living Earth" card format:
  - Photo in the upper portion
  - Optional circular inset photo (top-left)
  - White separator line + "ȘTIAI CĂ?" branding
  - Bold white uppercase text on solid black bottom band
Output size: 1080×1350 px (4:5 portrait — optimal for Facebook feed).
"""

import os
import textwrap
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ── Constants ────────────────────────────────────────────────────────────────
TARGET_W, TARGET_H = 1080, 1350
FONTS_DIR = os.path.join(os.path.dirname(__file__), "assets", "fonts")

PHOTO_RATIO = 0.55          # Photo takes top 55% of the canvas
BLACK_BAND_TOP = int(TARGET_H * PHOTO_RATIO)

BRAND_NAME = "ȘTIAI\nCĂ?"
BRAND_FONT_SIZE = 22
BRAND_COLOR = "#FFFFFF"
BRAND_SPACING = 4

LINE_COLOR = "#FFFFFF"
LINE_THICKNESS = 2
LINE_SIDE_MARGIN = 200      # How far the separator line extends from center

TITLE_COLOR = "#FFFFFF"
TITLE_FONT_SIZE = 72
TITLE_FONT_MIN = 44
SIDE_PADDING = 60
TITLE_TOP_PAD = 30          # Space between brand text and title

INSET_DIAMETER = 220        # Circular inset size
INSET_MARGIN = 30           # Margin from top-left corner
INSET_BORDER = 4            # White border around inset circle

CROP_VERTICAL_BIAS = 0.35   # Bias crop upward to keep subject visible


# ── Font helpers ─────────────────────────────────────────────────────────────

def _load_font(filename: str, size: int) -> ImageFont.FreeTypeFont:
    path = os.path.join(FONTS_DIR, filename)
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    for fallback in [
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        if os.path.exists(fallback):
            return ImageFont.truetype(fallback, size)
    return ImageFont.load_default()


def _text_width(text: str, font: ImageFont.FreeTypeFont) -> float:
    try:
        return font.getlength(text)
    except AttributeError:
        return len(text) * (font.size * 0.55)


def _text_height(text: str, font: ImageFont.FreeTypeFont) -> int:
    try:
        bbox = font.getbbox(text)
        return bbox[3] - bbox[1]
    except AttributeError:
        return int(font.size * 1.2)


# ── Image background helpers ─────────────────────────────────────────────────

def _crop_to_top(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Crop and resize photo to fill the top photo area, biasing upward."""
    src_w, src_h = img.size
    target_ratio = target_w / target_h

    if src_w / src_h > target_ratio:
        new_w = int(src_h * target_ratio)
        offset = (src_w - new_w) // 2
        img = img.crop((offset, 0, offset + new_w, src_h))
    else:
        new_h = int(src_w / target_ratio)
        offset = int((src_h - new_h) * CROP_VERTICAL_BIAS)
        img = img.crop((0, offset, src_w, offset + new_h))

    return img.resize((target_w, target_h), Image.LANCZOS)


def download_background(keywords: str, unsplash_key: str, save_path: str) -> str:
    resp = requests.get(
        "https://api.unsplash.com/photos/random",
        params={"query": keywords, "orientation": "portrait", "client_id": unsplash_key},
        timeout=20,
    )
    resp.raise_for_status()
    photo_url = resp.json()["urls"]["full"]

    img_resp = requests.get(photo_url, timeout=60)
    img_resp.raise_for_status()

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, "wb") as fh:
        fh.write(img_resp.content)
    return save_path


# ── Circular inset ───────────────────────────────────────────────────────────

def _make_circular_inset(img: Image.Image, diameter: int) -> Image.Image:
    """Crop image into a circle with a white border."""
    img = img.convert("RGBA")
    src_w, src_h = img.size
    side = min(src_w, src_h)
    left = (src_w - side) // 2
    top = (src_h - side) // 2
    img = img.crop((left, top, left + side, top + side))
    img = img.resize((diameter, diameter), Image.LANCZOS)

    mask = Image.new("L", (diameter, diameter), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, diameter - 1, diameter - 1), fill=255)

    result = Image.new("RGBA", (diameter, diameter), (0, 0, 0, 0))
    result.paste(img, mask=mask)

    border_img = Image.new("RGBA", (diameter, diameter), (0, 0, 0, 0))
    border_draw = ImageDraw.Draw(border_img)
    border_draw.ellipse(
        (0, 0, diameter - 1, diameter - 1),
        outline=(255, 255, 255, 255),
        width=INSET_BORDER,
    )
    result = Image.alpha_composite(result, border_img)
    return result


# ── Title text layout ────────────────────────────────────────────────────────

def _shorten_to_statement(text: str, max_sentences: int = 2) -> str:
    """Keep only the first 1-2 sentences for a punchy card headline."""
    sentences = []
    current = ""
    for ch in text:
        current += ch
        if ch in ".!?" and len(current.strip()) > 5:
            sentences.append(current.strip())
            current = ""
            if len(sentences) >= max_sentences:
                break
    if current.strip() and len(sentences) < max_sentences:
        sentences.append(current.strip())
    result = " ".join(sentences)
    if len(result) > 120 and len(sentences) > 1:
        result = sentences[0]
    return result


def _wrap_title(title: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    """Word-wrap title to fit within max_w pixels."""
    title = _shorten_to_statement(title)
    words = title.upper().split()
    lines, current = [], ""
    for word in words:
        candidate = (current + " " + word).strip()
        if _text_width(candidate, font) <= max_w:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [title.upper()]


def _fit_title(title: str, max_w: int, max_h: int) -> tuple[list[str], ImageFont.FreeTypeFont]:
    """Find the largest font size where the title fits both width and height."""
    for size in range(TITLE_FONT_SIZE, TITLE_FONT_MIN - 1, -2):
        font = _load_font("Montserrat-Bold.ttf", size)
        lines = _wrap_title(title, font, max_w)
        line_h = _text_height("AG", font)
        total_h = len(lines) * (line_h + 10)
        if total_h <= max_h:
            return lines, font

    font = _load_font("Montserrat-Bold.ttf", TITLE_FONT_MIN)
    lines = _wrap_title(title, font, max_w)
    return lines, font


# ── Main public function ──────────────────────────────────────────────────────

def generate_post_image(
    background_path: str,
    title: str,
    image_text: str,
    output_path: str,
    inset_path: str | None = None,
) -> str:
    """
    Create a 1080×1350 Facebook post image in card format.

    Layout:
      - Top 55%: photo (cropped to fit)
      - Optional circular inset in top-left
      - White separator line
      - "ȘTIAI CĂ?" brand text
      - Bold white uppercase title on solid black

    Args:
        background_path: Path to the main (close-up) photo.
        title:           The fact/curiosity heading shown in bold on the card.
        image_text:      (kept for API compat — not rendered on the new layout)
        output_path:     Where to save the generated JPEG.
        inset_path:      Optional path to a second photo for the circular inset.

    Returns:
        *output_path* on success.
    """
    photo_h = BLACK_BAND_TOP
    black_h = TARGET_H - photo_h

    # --- Build canvas ---
    canvas = Image.new("RGB", (TARGET_W, TARGET_H), (0, 0, 0))

    # Top photo
    bg = Image.open(background_path).convert("RGB")
    bg = _crop_to_top(bg, TARGET_W, photo_h)
    canvas.paste(bg, (0, 0))

    # Subtle gradient at bottom edge of photo for smooth transition
    gradient = Image.new("RGBA", (TARGET_W, 60), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(gradient)
    for y in range(60):
        alpha = int(255 * (y / 60) ** 1.5)
        gdraw.line([(0, y), (TARGET_W, y)], fill=(0, 0, 0, alpha))
    canvas.paste(
        Image.alpha_composite(
            canvas.crop((0, photo_h - 60, TARGET_W, photo_h)).convert("RGBA"),
            gradient,
        ).convert("RGB"),
        (0, photo_h - 60),
    )

    # Circular inset (top-left)
    if inset_path and os.path.exists(inset_path):
        inset_img = Image.open(inset_path).convert("RGBA")
        circle = _make_circular_inset(inset_img, INSET_DIAMETER)
        canvas.paste(
            circle,
            (INSET_MARGIN, INSET_MARGIN),
            mask=circle,
        )

    draw = ImageDraw.Draw(canvas)

    # --- Separator line ---
    line_y = photo_h + 30
    line_cx = TARGET_W // 2
    draw.line(
        [(line_cx - LINE_SIDE_MARGIN, line_y), (line_cx + LINE_SIDE_MARGIN, line_y)],
        fill=LINE_COLOR,
        width=LINE_THICKNESS,
    )

    # --- Brand text ---
    brand_font = _load_font("Montserrat-Bold.ttf", BRAND_FONT_SIZE)
    brand_y = line_y + 12
    for i, brand_line in enumerate(BRAND_NAME.split("\n")):
        bw = _text_width(brand_line, brand_font)
        draw.text(
            (line_cx - bw / 2, brand_y + i * (BRAND_FONT_SIZE + BRAND_SPACING)),
            brand_line,
            font=brand_font,
            fill=BRAND_COLOR,
        )
    brand_total_h = len(BRAND_NAME.split("\n")) * (BRAND_FONT_SIZE + BRAND_SPACING)

    # --- Title text ---
    title_area_top = brand_y + brand_total_h + TITLE_TOP_PAD
    title_area_bottom = TARGET_H - 40
    max_title_w = TARGET_W - 2 * SIDE_PADDING
    max_title_h = title_area_bottom - title_area_top

    title_lines, title_font = _fit_title(title, max_title_w, max_title_h)
    line_h = _text_height("AG", title_font)
    line_spacing = 10
    total_text_h = len(title_lines) * (line_h + line_spacing) - line_spacing

    # Center the title block vertically in the remaining space
    title_y = title_area_top + (max_title_h - total_text_h) // 2

    for line in title_lines:
        lw = _text_width(line, title_font)
        draw.text(
            ((TARGET_W - lw) / 2, title_y),
            line,
            font=title_font,
            fill=TITLE_COLOR,
        )
        title_y += line_h + line_spacing

    # --- Save ---
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    canvas.save(output_path, "JPEG", quality=95)
    print(f"[image_generator] Saved -> {output_path}")
    return output_path
