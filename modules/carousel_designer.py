"""
Carousel designer module: generates Instagram carousel images with Pillow.

Creates 1080x1350px slides with:
  - Gradient backgrounds
  - Structured text layout
  - Slide numbers / progress indicators
  - Accent lines and branding
  - Multiple rotating templates
"""

import logging
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from config.settings import (
    FONTS_DIR,
    INSTAGRAM_HANDLE,
    OUTPUT_DIR,
    SLIDE_HEIGHT,
    SLIDE_WIDTH,
)
from config.templates import FONT_SIZES, LAYOUT, TEMPLATES

logger = logging.getLogger(__name__)


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load a font at the given size. Falls back to default if custom fonts aren't available."""
    # Try custom fonts first
    font_names = (
        ["Inter-Bold.ttf", "Montserrat-Bold.ttf", "Arial Bold.ttf"]
        if bold
        else ["Inter-Regular.ttf", "Montserrat-Regular.ttf", "Arial.ttf"]
    )

    for name in font_names:
        font_path = FONTS_DIR / name
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size)

    # Try system fonts
    system_paths = [
        "/System/Library/Fonts/Helvetica.ttc",          # macOS
        "/System/Library/Fonts/SFPro.ttf",               # macOS
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
        "C:\\Windows\\Fonts\\arial.ttf",                  # Windows
    ]
    if bold:
        system_paths = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "C:\\Windows\\Fonts\\arialbd.ttf",
        ] + system_paths

    for path in system_paths:
        if Path(path).exists():
            return ImageFont.truetype(path, size)

    # Ultimate fallback
    return ImageFont.load_default()


def _draw_gradient(draw: ImageDraw.Draw, width: int, height: int, color_top: tuple, color_bottom: tuple):
    """Draw a vertical gradient on the image."""
    for y in range(height):
        ratio = y / height
        r = int(color_top[0] + (color_bottom[0] - color_top[0]) * ratio)
        g = int(color_top[1] + (color_bottom[1] - color_top[1]) * ratio)
        b = int(color_top[2] + (color_bottom[2] - color_top[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))


def _draw_text_wrapped(
    draw: ImageDraw.Draw,
    text: str,
    x: int,
    y: int,
    max_width: int,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    line_spacing: float = 1.4,
) -> int:
    """Draw text with word wrapping. Returns the Y position after the last line."""
    # Estimate characters per line based on font size
    avg_char_width = font.size * 0.55
    chars_per_line = max(1, int(max_width / avg_char_width))
    lines = textwrap.wrap(text, width=chars_per_line)

    current_y = y
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_height = bbox[3] - bbox[1]
        draw.text((x, current_y), line, font=font, fill=fill)
        current_y += int(line_height * line_spacing)

    return current_y


def _draw_accent_line(draw: ImageDraw.Draw, template: dict, y: int):
    """Draw a decorative accent line."""
    x = LAYOUT["padding_x"]
    width = LAYOUT["accent_line_width"]
    height = LAYOUT["accent_line_height"]
    draw.rectangle(
        [x, y, x + width, y + height],
        fill=template["accent_color"],
    )


def _draw_watermark(draw: ImageDraw.Draw, template: dict):
    """Draw the account handle as a subtle watermark."""
    font = _get_font(FONT_SIZES["watermark"])
    y = int(SLIDE_HEIGHT * LAYOUT["watermark_y"])
    bbox = draw.textbbox((0, 0), INSTAGRAM_HANDLE, font=font)
    text_width = bbox[2] - bbox[0]
    x = (SLIDE_WIDTH - text_width) // 2
    color = template["watermark_color"]
    draw.text((x, y), INSTAGRAM_HANDLE, font=font, fill=color)


def _draw_progress_dots(draw: ImageDraw.Draw, current: int, total: int, template: dict):
    """Draw progress indicator dots at the bottom of the slide."""
    dot_radius = 6
    dot_spacing = 24
    total_width = total * dot_spacing
    start_x = (SLIDE_WIDTH - total_width) // 2
    y = int(SLIDE_HEIGHT * 0.90)

    for i in range(total):
        cx = start_x + i * dot_spacing + dot_radius
        cy = y
        if i == current:
            draw.ellipse(
                [cx - dot_radius, cy - dot_radius, cx + dot_radius, cy + dot_radius],
                fill=template["accent_color"],
            )
        else:
            draw.ellipse(
                [cx - dot_radius, cy - dot_radius, cx + dot_radius, cy + dot_radius],
                fill=(*template["accent_color"][:3], 60) if len(template["accent_color"]) >= 3 else (100, 100, 100),
            )


# ── Slide Creators ───────────────────────────────────────────────────────────

def _create_cover_slide(slide: dict, template: dict, total_slides: int) -> Image.Image:
    """Create the cover/hook slide."""
    img = Image.new("RGBA", (SLIDE_WIDTH, SLIDE_HEIGHT))
    draw = ImageDraw.Draw(img)

    bg = template["background"]
    _draw_gradient(draw, SLIDE_WIDTH, SLIDE_HEIGHT, bg["color_top"], bg["color_bottom"])

    # Title
    title_font = _get_font(FONT_SIZES["cover_title"], bold=True)
    title_y = int(SLIDE_HEIGHT * 0.30)
    px = LAYOUT["padding_x"]
    max_w = SLIDE_WIDTH - 2 * px

    end_y = _draw_text_wrapped(draw, slide["title"], px, title_y, max_w, title_font, template["title_color"])

    # Accent line
    _draw_accent_line(draw, template, end_y + 20)

    # Subtitle
    if slide.get("subtitle"):
        subtitle_font = _get_font(FONT_SIZES["cover_subtitle"])
        _draw_text_wrapped(
            draw, slide["subtitle"], px, end_y + 50, max_w,
            subtitle_font, template["body_color"],
        )

    # Swipe indicator
    swipe_font = _get_font(22)
    swipe_text = "Desliza para más →"
    bbox = draw.textbbox((0, 0), swipe_text, font=swipe_font)
    sw = bbox[2] - bbox[0]
    draw.text(
        ((SLIDE_WIDTH - sw) // 2, int(SLIDE_HEIGHT * 0.85)),
        swipe_text,
        font=swipe_font,
        fill=(*template["accent_color"][:3], 180),
    )

    _draw_watermark(draw, template)
    return img


def _create_content_slide(
    slide: dict, template: dict, slide_index: int, total_slides: int
) -> Image.Image:
    """Create a content slide with title + body text."""
    img = Image.new("RGBA", (SLIDE_WIDTH, SLIDE_HEIGHT))
    draw = ImageDraw.Draw(img)

    bg = template["background"]
    _draw_gradient(draw, SLIDE_WIDTH, SLIDE_HEIGHT, bg["color_top"], bg["color_bottom"])

    px = LAYOUT["padding_x"]
    max_w = SLIDE_WIDTH - 2 * px

    # Slide number
    num_font = _get_font(FONT_SIZES["slide_number"], bold=True)
    number_text = f"{slide.get('number', slide_index)}/{total_slides - 2}"  # exclude cover and CTA
    draw.text(
        (px, int(SLIDE_HEIGHT * LAYOUT["slide_number_y"])),
        number_text,
        font=num_font,
        fill=template["slide_number_color"],
    )

    # Title
    title_font = _get_font(FONT_SIZES["slide_title"], bold=True)
    title_y = int(SLIDE_HEIGHT * LAYOUT["title_y"])
    end_y = _draw_text_wrapped(draw, slide.get("title", ""), px, title_y, max_w, title_font, template["title_color"])

    # Accent line
    _draw_accent_line(draw, template, end_y + 15)

    # Body text
    body_font = _get_font(FONT_SIZES["slide_body"])
    body_y = end_y + 45
    _draw_text_wrapped(
        draw, slide.get("body", ""), px, body_y, max_w,
        body_font, template["body_color"], line_spacing=LAYOUT["line_spacing"],
    )

    # Progress dots
    _draw_progress_dots(draw, slide_index, total_slides, template)

    _draw_watermark(draw, template)
    return img


def _create_cta_slide(slide: dict, template: dict, total_slides: int) -> Image.Image:
    """Create the call-to-action slide."""
    img = Image.new("RGBA", (SLIDE_WIDTH, SLIDE_HEIGHT))
    draw = ImageDraw.Draw(img)

    bg = template["background"]
    _draw_gradient(draw, SLIDE_WIDTH, SLIDE_HEIGHT, bg["color_top"], bg["color_bottom"])

    px = LAYOUT["padding_x"]
    max_w = SLIDE_WIDTH - 2 * px

    # CTA title
    title_font = _get_font(FONT_SIZES["cta_title"], bold=True)
    title_y = int(SLIDE_HEIGHT * 0.30)
    end_y = _draw_text_wrapped(draw, slide.get("title", ""), px, title_y, max_w, title_font, template["accent_color"])

    # Accent line
    _draw_accent_line(draw, template, end_y + 20)

    # CTA body
    body_font = _get_font(FONT_SIZES["cta_body"])
    body_y = end_y + 55
    _draw_text_wrapped(
        draw, slide.get("body", ""), px, body_y, max_w,
        body_font, template["body_color"], line_spacing=1.6,
    )

    # Handle prominent
    handle_font = _get_font(40, bold=True)
    bbox = draw.textbbox((0, 0), INSTAGRAM_HANDLE, font=handle_font)
    hw = bbox[2] - bbox[0]
    draw.text(
        ((SLIDE_WIDTH - hw) // 2, int(SLIDE_HEIGHT * 0.75)),
        INSTAGRAM_HANDLE,
        font=handle_font,
        fill=template["title_color"],
    )

    _draw_progress_dots(draw, total_slides - 1, total_slides, template)
    return img


# ── Main Entry Point ────────────────────────────────────────────────────────

def create(content: dict, template_index: int | None = None) -> list[Path]:
    """
    Create all carousel slide images.

    Args:
        content: dict from content_generator with 'slides' key
        template_index: optional index to force a specific template

    Returns:
        list of Path objects pointing to the generated PNG files
    """
    slides = content["slides"]
    total = len(slides)

    # Select template (rotate or use specified)
    if template_index is not None:
        template = TEMPLATES[template_index % len(TEMPLATES)]
    else:
        # Use a simple rotation based on how many files are in output
        existing = list(OUTPUT_DIR.glob("*.png"))
        template = TEMPLATES[len(existing) % len(TEMPLATES)]

    logger.info(f"Using template: {template['name']} for {total} slides")

    # Clear previous output
    for f in OUTPUT_DIR.glob("slide_*.png"):
        f.unlink()

    image_paths = []
    for i, slide in enumerate(slides):
        slide_type = slide.get("type", "content")

        if slide_type == "cover":
            img = _create_cover_slide(slide, template, total)
        elif slide_type == "cta":
            img = _create_cta_slide(slide, template, total)
        else:
            img = _create_content_slide(slide, template, i, total)

        # Convert RGBA to RGB for Instagram compatibility
        rgb_img = Image.new("RGB", img.size, (0, 0, 0))
        rgb_img.paste(img, mask=img.split()[3])

        path = OUTPUT_DIR / f"slide_{i:02d}.png"
        rgb_img.save(path, "PNG", quality=95)
        image_paths.append(path)
        logger.info(f"Saved: {path.name}")

    logger.info(f"Created {len(image_paths)} carousel images")
    return image_paths


# ── CLI Test Mode ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    # Test with sample content
    sample_content = {
        "slides": [
            {
                "type": "cover",
                "title": "🤖 OpenAI acaba de lanzar GPT-5",
                "subtitle": "Todo lo que necesitas saber en 60 segundos",
            },
            {
                "type": "content",
                "number": 1,
                "title": "40% más inteligente",
                "body": "GPT-5 supera a GPT-4 en un 40% en benchmarks de razonamiento lógico y matemático.",
            },
            {
                "type": "content",
                "number": 2,
                "title": "Pensamiento profundo 🧠",
                "body": "Nuevo modo de razonamiento que descompone problemas complejos paso a paso.",
            },
            {
                "type": "content",
                "number": 3,
                "title": "Multimodal total",
                "body": "Procesa texto, imagen, audio y video en una sola conversación sin cambiar de modelo.",
            },
            {
                "type": "content",
                "number": 4,
                "title": "50% más barato 💰",
                "body": "El precio de la API se reduce a la mitad respecto a GPT-4, democratizando el acceso.",
            },
            {
                "type": "content",
                "number": 5,
                "title": "Disponible ya",
                "body": "Accesible desde el día 1 en ChatGPT Plus y a través de la API para desarrolladores.",
            },
            {
                "type": "content",
                "number": 6,
                "title": "¿Un paso hacia AGI? 🌐",
                "body": "Sam Altman afirma que GPT-5 representa un avance significativo hacia la inteligencia artificial general.",
            },
            {
                "type": "cta",
                "title": "¿Te ha sido útil? 🔖",
                "body": "Guarda este post, compártelo y sígueme para más contenido sobre IA y tecnología cada día.",
            },
        ]
    }

    print("=" * 60)
    print("CAROUSEL DESIGNER — Test Mode")
    print("=" * 60)

    # Generate all 4 template variants for preview
    for t_idx in range(len(TEMPLATES)):
        paths = create(sample_content, template_index=t_idx)
        print(f"\nTemplate '{TEMPLATES[t_idx]['name']}': {len(paths)} slides saved")
        for p in paths:
            print(f"  → {p}")
