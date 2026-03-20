"""
cover_analyzer.py
Extracts the dominant color palette from the book's cover page and generates
a theme.json + a clean digital cover image.
"""

import fitz
import json
import io
from pathlib import Path
from typing import Optional
from collections import Counter

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def _luminance(r: int, g: int, b: int) -> float:
    """Relative luminance for determining text contrast."""
    def linearize(c):
        c /= 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)


def _contrast_ratio(l1: float, l2: float) -> float:
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _best_text_color(bg_hex: str) -> str:
    """Returns #ffffff or #1a1a1a depending on which has better contrast against bg."""
    r, g, b = int(bg_hex[1:3], 16), int(bg_hex[3:5], 16), int(bg_hex[5:7], 16)
    bg_lum = _luminance(r, g, b)
    white_contrast = _contrast_ratio(1.0, bg_lum)
    dark_contrast = _contrast_ratio(_luminance(26, 26, 26), bg_lum)
    return "#ffffff" if white_contrast >= dark_contrast else "#1a1a1a"


def extract_cover_palette(pdf_path: Path, dpi: int = 150) -> Optional[dict]:
    """
    Renders the first page (cover) of the PDF and extracts a 5-color palette.
    Returns a theme dict compatible with config.yaml and the React viewer.
    """
    if not PIL_AVAILABLE:
        print("  ⚠️  Pillow not installed. Skipping color extraction. Using default theme.")
        return None

    doc = fitz.open(str(pdf_path))
    page = doc[0]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
    doc.close()

    img = Image.open(io.BytesIO(pix.tobytes("png")))
    img = img.convert("RGB")

    # Resize to 100x100 for fast palette extraction
    small = img.resize((100, 100), Image.LANCZOS)
    pixels = list(small.getdata())

    # Quantize to a reduced palette
    quantized = img.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
    palette_raw = quantized.getpalette()[:24]  # 8 colors × 3 channels
    colors = [
        (palette_raw[i], palette_raw[i + 1], palette_raw[i + 2])
        for i in range(0, len(palette_raw), 3)
    ]

    # Sort by approximate visual weight (saturation × brightness)
    def saturation_brightness(rgb):
        r, g, b = [x / 255.0 for x in rgb]
        mx, mn = max(r, g, b), min(r, g, b)
        s = (mx - mn) / mx if mx > 0 else 0
        return s * mx

    colors.sort(key=saturation_brightness, reverse=True)
    hex_colors = [_rgb_to_hex(*c) for c in colors]

    # Map palette to semantic theme roles
    primary = hex_colors[0]
    secondary = hex_colors[1] if len(hex_colors) > 1 else "#64748b"
    accent = hex_colors[2] if len(hex_colors) > 2 else "#f59e0b"

    # Background: prefer a near-white/near-black from the palette
    bg_candidates = sorted(colors, key=lambda c: abs(_luminance(*c) - 0.95))
    bg_rgb = bg_candidates[0] if bg_candidates else (250, 250, 250)
    background = _rgb_to_hex(*bg_rgb)
    text_color = _best_text_color(background)

    theme = {
        "primary_color": primary,
        "secondary_color": secondary,
        "accent_color": accent,
        "background_color": background,
        "text_color": text_color,
        "palette": hex_colors[:8],
        "source": "auto-extracted from cover",
    }

    return theme


def save_cover_image(pdf_path: Path, output_path: Path, dpi: int = 200) -> bool:
    """Renders the first page and saves it as a clean PNG cover image."""
    try:
        doc = fitz.open(str(pdf_path))
        page = doc[0]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
        doc.close()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(output_path))
        print(f"  🖼️   Cover image saved → {output_path}")
        return True
    except Exception as e:
        print(f"  ⚠️   Could not save cover image: {e}")
        return False


def run_cover_analysis(pdf_path: Path, output_dir: Path, config_theme: dict) -> dict:
    """
    Full cover analysis pipeline.
    Returns final theme dict (config overrides take precedence over auto-extracted).
    """
    print("\n  🎨  Analyzing book cover for theme colors...")

    # Save cover image
    cover_path = output_dir / "cover.png"
    save_cover_image(pdf_path, cover_path)

    # Extract palette
    auto_theme = extract_cover_palette(pdf_path) or {}

    # Merge: config values override auto-extracted
    final_theme = {**auto_theme}
    for key in ["primary_color", "secondary_color", "accent_color", "background_color", "text_color"]:
        if config_theme.get(key):
            final_theme[key] = config_theme[key]
            final_theme["source"] = "manually configured"

    # Save theme.json
    theme_path = output_dir / "theme.json"
    theme_path.write_text(json.dumps(final_theme, indent=2))
    print(f"  🎨  Theme saved → {theme_path}")
    print(f"      Primary: {final_theme.get('primary_color', 'n/a')}  "
          f"Secondary: {final_theme.get('secondary_color', 'n/a')}  "
          f"Accent: {final_theme.get('accent_color', 'n/a')}")

    return final_theme
