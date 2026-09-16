"""
Stage 3: poster compositor.

Takes a DALL-E background image and lays the genotype's headline,
subtext, call-to-action, and QR code (from Stage 2) on top with Pillow.
This is what turns raw AI artwork into an actual, scannable poster.

A couple of decisions worth calling out:

- Headline/subtext sit on a semi-transparent black band rather than
  directly on the artwork. AI-generated backgrounds have unpredictable
  brightness and busyness, so plain white text on top of them would
  sometimes be illegible -- the band guarantees contrast regardless of
  what DALL-E produced.
- The QR code always gets a solid white "quiet zone" card behind it.
  QR scanners need a clean margin of contrast around the code to read it
  reliably; pasting one directly onto photographic artwork risks
  producing an unscannable poster (exactly what Stage 7's quality gate
  will later check for).
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_DIR = Path("C:/Windows/Fonts")

TYPOGRAPHY_FONTS = {
    "bold_sans": {"heavy": "arialbd.ttf", "regular": "arial.ttf"},
    "elegant_serif": {"heavy": "georgiab.ttf", "regular": "georgia.ttf"},
    "hand_drawn": {"heavy": "comicbd.ttf", "regular": "comic.ttf"},
    "mixed": {"heavy": "georgiab.ttf", "regular": "arial.ttf"},
    "condensed": {"heavy": "ARIALNB.TTF", "regular": "ARIALN.TTF"},
}

COLOUR_ACCENTS = {
    "dark_neon_accent": "#39FF88",
    "black_white_red": "#E10600",
    "warm_tones": "#D97706",
    "cool_tones": "#2563EB",
    "monochrome": "#666666",
}

CTA_PROMINENCE_STYLE = {
    "dominant": {"font_scale": 1.0, "pill": True},
    "subordinate": {"font_scale": 0.6, "pill": False},
    "integrated": {"font_scale": 0.8, "pill": False},
}

QR_SCALE = {
    "dominant_centre": 0.30,
    "bottom_right": 0.17,
    "bottom_centre": 0.17,
    "integrated": 0.17,
}


def get_font(typography_style: str, weight: str, size: int) -> ImageFont.FreeTypeFont:
    """
    Look up the font file for a typography_style/weight pair and load it at
    `size`. Falls back to Pillow's built-in font if the file isn't found --
    keeps this working on a non-Windows machine, just less styled.
    """
    fonts = TYPOGRAPHY_FONTS.get(typography_style, TYPOGRAPHY_FONTS["bold_sans"])
    font_path = FONT_DIR / fonts[weight]
    try:
        return ImageFont.truetype(str(font_path), size)
    except OSError:
        return ImageFont.load_default(size)


def _is_light(hex_colour: str) -> bool:
    """True if hex_colour is light enough that black text reads better on it than white."""
    hex_colour = hex_colour.lstrip("#")
    r, g, b = (int(hex_colour[i : i + 2], 16) for i in (0, 2, 4))
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return luminance > 0.6


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Break `text` into lines that each fit within max_width when rendered in `font`."""
    lines = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if not current or draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def compute_qr_card_geometry(width: int, height: int, qr_placement: str) -> dict:
    """
    Returns the geometry of the QR's white quiet-zone card, given the
    canvas size and placement: {card_x, card_y, card_size, qr_size,
    padding}. Pulled out as its own function so Stage 7's quality gate can
    find the exact same region this module draws the QR into -- without
    it, a QR-readability check on the full poster has to search the whole
    image for a small code, which OpenCV's detector is bad at even when
    the code is perfectly scannable up close (verified: a poster that
    "failed" QR detection decoded correctly the moment it was cropped to
    this exact region).
    """
    qr_scale = QR_SCALE.get(qr_placement, 0.17)
    qr_size = int(min(width, height) * qr_scale)
    padding = int(qr_size * 0.12)
    card_size = qr_size + 2 * padding
    margin = int(width * 0.06)

    positions = {
        "bottom_right": (width - card_size - margin, height - card_size - margin),
        "bottom_centre": ((width - card_size) // 2, height - card_size - margin),
        "integrated": (margin, height - card_size - margin),
        "dominant_centre": ((width - card_size) // 2, (height - card_size) // 2),
    }
    card_x, card_y = positions.get(qr_placement, positions["bottom_right"])
    return {"card_x": card_x, "card_y": card_y, "card_size": card_size, "qr_size": qr_size, "padding": padding}


def _draw_centered_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font: ImageFont.FreeTypeFont,
    center_x: float,
    top_y: float,
    fill: str,
    line_spacing: float = 1.2,
) -> float:
    """Draw each line horizontally centered on center_x, stacked downward from top_y. Returns the y just below the last line."""
    y = top_y
    for line in lines:
        left, top, right, bottom = draw.textbbox((0, 0), line, font=font)
        width, height = right - left, bottom - top
        draw.text((center_x - width / 2, y), line, font=font, fill=fill)
        y += height * line_spacing
    return y


def compose_poster(genotype: dict, background_path: Path, qr_image_path: Path, output_path: Path) -> Path:
    """
    Composite one finished poster: background artwork + headline/subtext
    band + call-to-action + QR code, laid out according to the genotype's
    typography_style, colour_scheme, cta_prominence, and qr_placement.
    Saves the result to output_path and returns it.
    """
    image = Image.open(background_path).convert("RGBA")
    width, height = image.size
    draw = ImageDraw.Draw(image, "RGBA")
    margin = int(width * 0.06)
    accent = COLOUR_ACCENTS.get(genotype["colour_scheme"], "#FFFFFF")

    # --- headline / subtext band ---
    band_height = int(height * 0.24)
    draw.rectangle([0, 0, width, band_height], fill=(0, 0, 0, 160))

    headline_font = get_font(genotype["typography_style"], "heavy", int(height * 0.05))
    headline_lines = _wrap_text(draw, genotype["headline"], headline_font, width - 2 * margin)
    next_y = _draw_centered_lines(draw, headline_lines, headline_font, width / 2, int(height * 0.03), fill="white")

    if genotype.get("subtext"):
        subtext_font = get_font(genotype["typography_style"], "regular", int(height * 0.028))
        subtext_lines = _wrap_text(draw, genotype["subtext"], subtext_font, width - 2 * margin)
        _draw_centered_lines(draw, subtext_lines, subtext_font, width / 2, next_y + int(height * 0.015), fill="white")

    # --- QR code, on its own white quiet-zone card for scannability ---
    geometry = compute_qr_card_geometry(width, height, genotype["qr_placement"])
    card_x, card_y, card_size = geometry["card_x"], geometry["card_y"], geometry["card_size"]
    qr_size, padding = geometry["qr_size"], geometry["padding"]

    draw.rounded_rectangle(
        [card_x, card_y, card_x + card_size, card_y + card_size],
        radius=int(card_size * 0.08),
        fill=(255, 255, 255, 255),
    )
    qr = Image.open(qr_image_path).convert("RGBA").resize((qr_size, qr_size))
    image.paste(qr, (card_x + padding, card_y + padding), qr)

    # --- call to action, anchored just above the QR card ---
    cta_text = genotype.get("call_to_action", "")
    if cta_text:
        style = CTA_PROMINENCE_STYLE.get(genotype["cta_prominence"], CTA_PROMINENCE_STYLE["integrated"])
        cta_font = get_font(genotype["typography_style"], "heavy", int(height * 0.032 * style["font_scale"]))
        left, top, right, bottom = draw.textbbox((0, 0), cta_text, font=cta_font)
        text_w, text_h = right - left, bottom - top
        pad_x, pad_y = int(text_w * 0.25), int(text_h * 0.4)

        # Anchored above the QR card by default, but clamped so the pill
        # never extends past the canvas edges -- a wide CTA string (e.g.
        # "Reserve your spot") paired with an edge-hugging qr_placement
        # like bottom_right previously got silently clipped by Pillow,
        # which draws happily off-canvas with no error or warning.
        pill_half_width = text_w / 2 + pad_x
        min_center = margin + pill_half_width
        max_center = width - margin - pill_half_width
        cta_center_x = card_x + card_size / 2
        if min_center <= max_center:
            cta_center_x = max(min_center, min(cta_center_x, max_center))
        else:
            cta_center_x = width / 2  # text too wide to fit within margins either way -- center it as a fallback
        cta_top = card_y - text_h - pad_y * 2 - int(height * 0.015)

        chip_fill = accent if style["pill"] else (0, 0, 0, 160)
        text_fill = "black" if style["pill"] and _is_light(accent) else "white"

        draw.rounded_rectangle(
            [
                cta_center_x - text_w / 2 - pad_x,
                cta_top,
                cta_center_x + text_w / 2 + pad_x,
                cta_top + text_h + pad_y * 2,
            ],
            radius=text_h,
            fill=chip_fill,
        )
        draw.text((cta_center_x - text_w / 2, cta_top + pad_y), cta_text, font=cta_font, fill=text_fill)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(output_path)
    return output_path
