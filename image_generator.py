"""
image_generator.py
Generates styled Facebook post images: background photo + gradient overlay + text.
Output size: 1080×1350 px (4:5 portrait — optimal for Facebook feed).
"""

import os
import textwrap
from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageFont

# ── Constants ────────────────────────────────────────────────────────────────
TARGET_W, TARGET_H = 1080, 1350
FONTS_DIR = os.path.join(os.path.dirname(__file__), "assets", "fonts")

TITLE_COLOR   = "#F5C518"   # Gold/yellow — matches the example style
BODY_COLOR    = "#FFFFFF"
SHADOW_COLOR  = (0, 0, 0, 160)

GRADIENT_START_RATIO  = 0.48   # Gradient begins mid-frame; subject stays in upper half
SOLID_START_RATIO     = 0.58   # Bottom text band — sized to fit wrapped body copy
GRADIENT_MAX_ALPHA    = 255
CROP_VERTICAL_BIAS    = 0.62   # Shift crop down so subject sits in upper half

TITLE_FONT_SIZE = 96    # Max size; auto-shrinks for long titles
TITLE_FONT_MIN  = 56
BODY_FONT_SIZE  = 42
BODY_FONT_MIN   = 26
LINE_SPACING    = 10
LINE_SPACING_MIN = 4
SIDE_PADDING    = 56
BOTTOM_PADDING  = 48
TEXT_AREA_TOP_PAD = 16
GAP_TITLE_BODY  = 24


# ── Font helpers ─────────────────────────────────────────────────────────────

def _load_font(filename: str, size: int) -> ImageFont.FreeTypeFont:
    path = os.path.join(FONTS_DIR, filename)
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    # Fallback: try common Windows system fonts
    for fallback in [
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        if os.path.exists(fallback):
            return ImageFont.truetype(fallback, size)
    return ImageFont.load_default()


def _get_fonts():
    title_font = _load_font("Montserrat-Bold.ttf", TITLE_FONT_SIZE)
    body_font  = _load_font("Montserrat-Regular.ttf", BODY_FONT_SIZE)
    return title_font, body_font


def _text_width(text: str, font: ImageFont.FreeTypeFont) -> float:
    try:
        return font.getlength(text)
    except AttributeError:
        return len(text) * (font.size * 0.55)


def _fit_title(title: str) -> tuple[list[str], ImageFont.FreeTypeFont]:
    """Shrink font and/or split title so it fits within the image width."""
    max_w = TARGET_W - 2 * SIDE_PADDING
    words = title.split()

    for size in range(TITLE_FONT_SIZE, TITLE_FONT_MIN - 1, -2):
        font = _load_font("Montserrat-Bold.ttf", size)
        if _text_width(title, font) <= max_w:
            return [title], font

        if len(words) >= 2:
            for split in range(1, len(words)):
                line1 = " ".join(words[:split])
                line2 = " ".join(words[split:])
                if _text_width(line1, font) <= max_w and _text_width(line2, font) <= max_w:
                    return [line1, line2], font

    font = _load_font("Montserrat-Bold.ttf", TITLE_FONT_MIN)
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
    return lines or [title], font


# ── Image background helpers ─────────────────────────────────────────────────

def _crop_center(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Crop + resize to 4:5, biasing upward so the subject stays above the text overlay."""
    src_w, src_h = img.size
    target_ratio = target_w / target_h
    src_ratio    = src_w / src_h

    if src_ratio > target_ratio:
        new_w = int(src_h * target_ratio)
        offset = (src_w - new_w) // 2
        img = img.crop((offset, 0, offset + new_w, src_h))
    else:
        new_h = int(src_w / target_ratio)
        offset = int((src_h - new_h) * CROP_VERTICAL_BIAS)
        img = img.crop((0, offset, src_w, offset + new_h))

    return img.resize((target_w, target_h), Image.LANCZOS)


def download_background(keywords: str, unsplash_key: str, save_path: str) -> str:
    """
    Fetch a portrait photo from Unsplash matching *keywords* and save it.
    Returns *save_path* on success.
    """
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


# ── Gradient overlay ─────────────────────────────────────────────────────────

def _apply_gradient(img: Image.Image) -> Image.Image:
    """
    Blend a dark-to-transparent gradient over the bottom portion of the image.
    Returns a new RGB image.
    """
    overlay = Image.new("RGBA", (TARGET_W, TARGET_H), (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)
    start_y = int(TARGET_H * GRADIENT_START_RATIO)

    solid_y = int(TARGET_H * SOLID_START_RATIO)
    for y in range(start_y, TARGET_H):
        if y >= solid_y:
            alpha = GRADIENT_MAX_ALPHA
        else:
            progress = (y - start_y) / (solid_y - start_y)
            alpha = int(GRADIENT_MAX_ALPHA * (progress ** 0.7))
        draw.line([(0, y), (TARGET_W, y)], fill=(0, 0, 0, alpha))

    base = img.convert("RGBA")
    return Image.alpha_composite(base, overlay).convert("RGB")


# ── Text drawing ─────────────────────────────────────────────────────────────

def _line_height(font: ImageFont.FreeTypeFont, spacing: int = LINE_SPACING) -> int:
    """Pixel height of one text line including spacing below it."""
    ascent, descent = font.getmetrics()
    return ascent + descent + spacing


def _title_block_height(lines: list[str], font: ImageFont.FreeTypeFont) -> int:
    if not lines:
        return 0
    line_h = _line_height(font, spacing=8)
    return len(lines) * line_h + 12


def _body_block_height(lines: list[str], font: ImageFont.FreeTypeFont, spacing: int) -> int:
    if not lines:
        return 0
    return len(lines) * _line_height(font, spacing)


def _draw_text_with_shadow(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: str,
    shadow_offset: int = 3,
) -> None:
    x, y = xy
    draw.text((x + shadow_offset, y + shadow_offset), text, font=font,
              fill=(0, 0, 0, 160), anchor="mt")
    draw.text((x, y), text, font=font, fill=fill, anchor="mt")


def _wrap_body_text(
    text: str,
    body_font: ImageFont.FreeTypeFont,
    max_lines: int | None = None,
) -> list[str]:
    """
    Wrap text to fit within (TARGET_W - 2*SIDE_PADDING) pixels.
    Falls back to character-based wrapping if bbox is unavailable.
    """
    max_w = TARGET_W - 2 * SIDE_PADDING
    words = text.split()
    lines, current = [], ""

    for word in words:
        candidate = (current + " " + word).strip()
        try:
            w = body_font.getlength(candidate)
        except AttributeError:
            w = len(candidate) * (body_font.size * 0.55)

        if w <= max_w:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        trimmed = lines[-1].rstrip(".,;:!? ")
        lines[-1] = trimmed + "…"

    return lines


def _text_area_bounds() -> tuple[int, int]:
    """Return (top, bottom) y-coordinates of the usable text band."""
    top = int(TARGET_H * SOLID_START_RATIO) + TEXT_AREA_TOP_PAD
    bottom = TARGET_H - BOTTOM_PADDING
    return top, bottom


def _fit_body_layout(
    image_text: str,
    title_lines: list[str],
    title_font: ImageFont.FreeTypeFont,
) -> tuple[list[str], ImageFont.FreeTypeFont, int]:
    """
    Pick body font size, line spacing, and line count so the full text block
    fits inside the bottom overlay without clipping.
    """
    text_top, text_bottom = _text_area_bounds()
    max_total_h = text_bottom - text_top
    title_block_h = _title_block_height(title_lines, title_font)
    max_body_h = max_total_h - title_block_h - GAP_TITLE_BODY

    if max_body_h <= 0:
        font = _load_font("Montserrat-Regular.ttf", BODY_FONT_MIN)
        return _wrap_body_text(image_text, font, max_lines=1), font, LINE_SPACING_MIN

    best_lines: list[str] = []
    best_font = _load_font("Montserrat-Regular.ttf", BODY_FONT_MIN)
    best_spacing = LINE_SPACING_MIN

    for size in range(BODY_FONT_SIZE, BODY_FONT_MIN - 1, -2):
        body_font = _load_font("Montserrat-Regular.ttf", size)
        lines = _wrap_body_text(image_text, body_font)

        for spacing in range(LINE_SPACING, LINE_SPACING_MIN - 1, -2):
            block_h = _body_block_height(lines, body_font, spacing)
            if block_h <= max_body_h:
                return lines, body_font, spacing

        best_lines, best_font, best_spacing = lines, body_font, LINE_SPACING_MIN

    # Still too tall at minimum size — keep as many lines as fit, with ellipsis.
    for max_lines in range(len(best_lines), 0, -1):
        lines = _wrap_body_text(image_text, best_font, max_lines=max_lines)
        if _body_block_height(lines, best_font, best_spacing) <= max_body_h:
            return lines, best_font, best_spacing

    font = _load_font("Montserrat-Regular.ttf", BODY_FONT_MIN)
    return _wrap_body_text(image_text, font, max_lines=1), font, LINE_SPACING_MIN


# ── Main public function ──────────────────────────────────────────────────────

def generate_post_image(
    background_path: str,
    title: str,
    image_text: str,
    output_path: str,
) -> str:
    """
    Create a 1080×1350 Facebook post image.

    Args:
        background_path: Path to the source photo.
        title:           Large heading text (e.g. "Margareta").
        image_text:      5-6 sentences shown ON the image (detailed curiosity teaser).
        output_path:     Where to save the generated JPEG.

    Returns:
        *output_path* on success.
    """
    _, body_font = _get_fonts()
    title_lines, title_font = _fit_title(title)
    body_lines, body_font, line_spacing = _fit_body_layout(
        image_text, title_lines, title_font
    )

    # Prepare background
    bg = Image.open(background_path).convert("RGB")
    bg = _crop_center(bg, TARGET_W, TARGET_H)
    bg = _apply_gradient(bg)

    draw = ImageDraw.Draw(bg)

    title_block_h = _title_block_height(title_lines, title_font)
    body_block_h  = _body_block_height(body_lines, body_font, line_spacing)
    total_h = title_block_h + GAP_TITLE_BODY + body_block_h

    text_top, text_bottom = _text_area_bounds()
    text_band_h = text_bottom - text_top
    start_y = text_top + max(0, (text_band_h - total_h) // 2)

    cx = TARGET_W // 2  # horizontal center
    title_line_h = _line_height(title_font, spacing=8)

    # Draw title (one or two lines, auto-sized)
    title_y = start_y
    for line in title_lines:
        _draw_text_with_shadow(draw, (cx, title_y), line, title_font, TITLE_COLOR)
        title_y += title_line_h

    # Draw body lines
    body_y = start_y + title_block_h + GAP_TITLE_BODY
    body_line_h = _line_height(body_font, spacing=line_spacing)
    for line in body_lines:
        _draw_text_with_shadow(draw, (cx, body_y), line, body_font, BODY_COLOR)
        body_y += body_line_h

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    bg.save(output_path, "JPEG", quality=95)
    print(f"[image_generator] Saved → {output_path}")
    return output_path
