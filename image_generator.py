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

GRADIENT_START_RATIO  = 0.50   # Photo in top half; gradient begins at 50%
SOLID_START_RATIO     = 0.56   # Solid black under text from 56% down
GRADIENT_MAX_ALPHA    = 255
CROP_VERTICAL_BIAS    = 0.62   # Shift crop down so subject sits in upper half

TITLE_FONT_SIZE = 96    # Max size; auto-shrinks for long titles
TITLE_FONT_MIN  = 56
BODY_FONT_SIZE  = 48
BODY_FONT_MIN   = 46
LINE_SPACING    = 10
SIDE_PADDING    = 56
MAX_BODY_LINES  = 6           # Hard cap: 5-6 visible lines under the title
TEXT_BAND_TOP_PAD    = 24
TEXT_BAND_BOTTOM_PAD = 88   # Safe margin for descenders (g, y, p)
TEXT_FIT_MARGIN      = 12


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

def _text_block_height(lines: list[str], body_font: ImageFont.FreeTypeFont) -> int:
    """Total pixel height of all body text lines."""
    _, _, _, lh = body_font.getbbox("Ag")
    line_height = lh + LINE_SPACING
    return len(lines) * line_height


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


def _wrap_body_text(text: str, body_font: ImageFont.FreeTypeFont) -> list[str]:
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
            w = len(candidate) * (BODY_FONT_SIZE * 0.55)

        if w <= max_w:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines[:MAX_BODY_LINES]


def _measure_layout(
    title_lines: list[str],
    title_font: ImageFont.FreeTypeFont,
    body_lines: list[str],
    body_font: ImageFont.FreeTypeFont,
) -> tuple[int, int, int, int]:
    """Return (title_block_h, body_line_h, body_block_h, total_h)."""
    _, _, _, title_lh = title_font.getbbox("Ag")
    title_block_h = len(title_lines) * (title_lh + 8) + 12
    _, _, _, body_lh = body_font.getbbox("Ag")
    body_line_h = body_lh + LINE_SPACING
    body_block_h = len(body_lines) * body_line_h
    gap = 24
    total_h = title_block_h + gap + body_block_h
    return title_block_h, body_line_h, body_block_h, total_h


def _truncate_to_max_lines(
    text: str, body_font: ImageFont.FreeTypeFont, max_lines: int = MAX_BODY_LINES
) -> tuple[str, list[str]]:
    """Trim words until wrapped text fits in *max_lines*."""
    words = text.split()
    if not words:
        return text, []
    while words:
        candidate = " ".join(words)
        lines = _wrap_body_text(candidate, body_font)
        if len(lines) <= max_lines:
            return candidate, lines
        words.pop()
    return words[0] if words else text, _wrap_body_text(words[0], body_font)[:max_lines]


def _fit_body_to_band(
    image_text: str,
    title_lines: list[str],
    title_font: ImageFont.FreeTypeFont,
    band_h: int,
) -> tuple[list[str], ImageFont.FreeTypeFont, int, int, int, int]:
    """Use large body font; never exceed MAX_BODY_LINES."""
    body_font = _load_font("Montserrat-Regular.ttf", BODY_FONT_SIZE)
    _, body_lines = _truncate_to_max_lines(image_text, body_font, MAX_BODY_LINES)
    title_block_h, body_line_h, body_block_h, total_h = _measure_layout(
        title_lines, title_font, body_lines, body_font
    )

    if total_h > band_h - TEXT_FIT_MARGIN:
        body_font = _load_font("Montserrat-Regular.ttf", BODY_FONT_MIN)
        _, body_lines = _truncate_to_max_lines(image_text, body_font, MAX_BODY_LINES)
        title_block_h, body_line_h, body_block_h, total_h = _measure_layout(
            title_lines, title_font, body_lines, body_font
        )

    return body_lines, body_font, title_block_h, body_line_h, body_block_h, total_h


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
    title_font, body_font = _get_fonts()
    title_lines, title_font = _fit_title(title)

    # Prepare background
    bg = Image.open(background_path).convert("RGB")
    bg = _crop_center(bg, TARGET_W, TARGET_H)
    bg = _apply_gradient(bg)

    draw = ImageDraw.Draw(bg)

    band_top = int(TARGET_H * GRADIENT_START_RATIO) + TEXT_BAND_TOP_PAD
    band_bottom = TARGET_H - TEXT_BAND_BOTTOM_PAD
    band_h = band_bottom - band_top

    body_lines, body_font, title_block_h, body_line_h, body_block_h, total_h = _fit_body_to_band(
        image_text, title_lines, title_font, band_h
    )

    gap_title_body = 24
    if total_h >= band_h * 0.82:
        start_y = band_top
    else:
        start_y = band_top + max(0, (band_h - total_h) // 5)

    content_bottom = start_y + title_block_h + gap_title_body + len(body_lines) * body_line_h + 6
    if content_bottom > band_bottom:
        start_y = max(band_top, start_y - (content_bottom - band_bottom))

    cx = TARGET_W // 2  # horizontal center

    # Draw title (one or two lines, auto-sized)
    _, _, _, title_lh = title_font.getbbox("Ag")
    title_y = start_y
    for line in title_lines:
        _draw_text_with_shadow(draw, (cx, title_y), line, title_font, TITLE_COLOR)
        title_y += title_lh + 8

    # Draw body lines
    body_y = start_y + title_block_h + gap_title_body
    for line in body_lines:
        _draw_text_with_shadow(draw, (cx, body_y), line, body_font, BODY_COLOR)
        body_y += body_line_h

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    bg.save(output_path, "JPEG", quality=95)
    print(f"[image_generator] Saved → {output_path}")
    return output_path
