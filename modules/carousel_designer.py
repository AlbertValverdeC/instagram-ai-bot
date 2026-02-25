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

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import re

from config.settings import (
    FONTS_DIR,
    INSTAGRAM_HANDLE,
    OUTPUT_DIR,
    PROFILE_PIC_PATH,
    SLIDE_HEIGHT,
    SLIDE_WIDTH,
)
from config.templates import FONT_SIZES, LAYOUT, TEMPLATES

logger = logging.getLogger(__name__)


_VARIABLE_FONT = FONTS_DIR / "SpaceGrotesk-Regular.ttf"


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load Space Grotesk at the given size/weight. Falls back to system fonts."""
    # Preferred: Space Grotesk variable font
    if _VARIABLE_FONT.exists():
        try:
            font = ImageFont.truetype(str(_VARIABLE_FONT), size)
            font.set_variation_by_name("Bold" if bold else "Regular")
            return font
        except Exception:
            pass

    # Fallback: static font files
    font_names = (
        ["SpaceGrotesk-Bold.ttf", "Inter-Bold.ttf", "Montserrat-Bold.ttf"]
        if bold
        else ["SpaceGrotesk-Regular.ttf", "Inter-Regular.ttf", "Montserrat-Regular.ttf"]
    )

    for name in font_names:
        font_path = FONTS_DIR / name
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size)

    # System fonts
    system_paths = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFPro.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
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
    highlight_color: tuple | None = None,
) -> int:
    """Draw left-aligned text with word wrapping and optional **highlight** support.

    Text wrapped in **double asterisks** renders in highlight_color with an underline.
    Returns the Y position after the last line.
    """
    # Strip ** markers if no highlight color — render plain
    if highlight_color is None:
        clean = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        avg_char_width = font.size * 0.55
        chars_per_line = max(1, int(max_width / avg_char_width))
        lines = textwrap.wrap(clean, width=chars_per_line)
        current_y = y
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_height = bbox[3] - bbox[1]
            draw.text((x, current_y), line, font=font, fill=fill)
            current_y += int(line_height * line_spacing)
        return current_y

    # Parse **highlight** segments into (word, is_highlighted) list
    segments = _parse_bicolor_text(text)
    words = []
    for seg_text, is_hl in segments:
        for w in seg_text.split():
            words.append((w, is_hl))

    # Wrap into lines based on pixel width
    space_width = draw.textbbox((0, 0), " ", font=font)[2]
    lines = []
    current_line = []
    current_width = 0

    for word, is_hl in words:
        word_w = draw.textbbox((0, 0), word, font=font)[2]
        needed = word_w + (space_width if current_line else 0)
        if current_line and current_width + needed > max_width:
            lines.append(current_line)
            current_line = [(word, is_hl)]
            current_width = word_w
        else:
            current_line.append((word, is_hl))
            current_width += needed
    if current_line:
        lines.append(current_line)

    # Draw each line left-aligned with highlight color + underline
    underline_thickness = max(2, font.size // 16)
    underline_gap = 4
    current_y = y
    for line_words in lines:
        line_text = " ".join(w for w, _ in line_words)
        bbox = draw.textbbox((0, 0), line_text, font=font)
        line_h = bbox[3] - bbox[1]
        cursor_x = x

        for word, is_hl in line_words:
            color = highlight_color if is_hl else fill
            draw.text((cursor_x, current_y), word, font=font, fill=color)
            word_bbox = draw.textbbox((0, 0), word, font=font)
            word_w = word_bbox[2] - word_bbox[0]

            if is_hl:
                ul_y = current_y + line_h + underline_gap
                draw.rectangle(
                    [cursor_x, ul_y, cursor_x + word_w, ul_y + underline_thickness],
                    fill=highlight_color,
                )

            cursor_x += word_w + space_width

        current_y += int(line_h * line_spacing)

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


def _draw_branded_footer(img: Image.Image, draw: ImageDraw.Draw, template: dict):
    """Draw a branded footer bar at the bottom of the slide."""
    accent = template["accent_color"]
    px = LAYOUT["padding_x"]
    footer_y = int(SLIDE_HEIGHT * 0.93)

    # Thin accent line spanning most of the width
    line_y = footer_y - 8
    draw.line(
        [(px, line_y), (SLIDE_WIDTH - px, line_y)],
        fill=(*accent[:3], 80),
        width=1,
    )

    # Handle text — left-aligned, with accent dot before it
    handle_font = _get_font(22, bold=True)
    dot_r = 5
    dot_x = px + dot_r
    dot_y = footer_y + 10
    draw.ellipse(
        [dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r],
        fill=accent,
    )

    handle_x = dot_x + dot_r + 10
    draw.text(
        (handle_x, footer_y),
        INSTAGRAM_HANDLE,
        font=handle_font,
        fill=(255, 255, 255, 180),
    )

    # Profile pic in footer (small, right side)
    if PROFILE_PIC_PATH is not None:
        try:
            pic = Image.open(PROFILE_PIC_PATH).convert("RGBA")
            pic_size = 32
            pic = pic.resize((pic_size, pic_size), Image.LANCZOS)
            mask = Image.new("L", (pic_size, pic_size), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, pic_size, pic_size], fill=255)
            circle = Image.new("RGBA", (pic_size, pic_size), (0, 0, 0, 0))
            circle.paste(pic, (0, 0), mask)
            pic_x = SLIDE_WIDTH - px - pic_size
            pic_y = footer_y - 2
            img.paste(circle, (pic_x, pic_y), circle)
        except Exception:
            pass


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

def _parse_bicolor_text(text: str) -> list[tuple[str, bool]]:
    """Parse text with **highlight** markers into segments.

    Returns list of (text, is_highlighted) tuples.
    Example: "AQUÍ TIENES LAS **NOTICIAS MÁS IMPORTANTES** DE HOY"
    → [("AQUÍ TIENES LAS ", False), ("NOTICIAS MÁS IMPORTANTES", True), (" DE HOY", False)]
    """
    segments = []
    parts = re.split(r'\*\*(.+?)\*\*', text)
    for i, part in enumerate(parts):
        if part:
            segments.append((part, i % 2 == 1))  # odd indices are inside **
    return segments


def _draw_bicolor_text_centered(
    draw: ImageDraw.Draw,
    text: str,
    y: int,
    max_width: int,
    font: ImageFont.FreeTypeFont,
    normal_color: tuple,
    highlight_color: tuple,
    line_spacing: float = 1.25,
) -> int:
    """Draw centered text with bicolor highlighting. Returns Y after last line.

    Words wrapped in **double asterisks** render in highlight_color, rest in normal_color.
    """
    # Parse the bicolor segments
    segments = _parse_bicolor_text(text)

    # Build flat list of (word, is_highlighted) preserving spaces
    words = []
    for seg_text, is_hl in segments:
        seg_words = seg_text.split()
        for j, w in enumerate(seg_words):
            words.append((w, is_hl))

    # Wrap into lines based on max_width
    lines = []  # each line is a list of (word, is_highlighted)
    current_line = []
    current_width = 0
    space_width = draw.textbbox((0, 0), " ", font=font)[2]

    for word, is_hl in words:
        word_bbox = draw.textbbox((0, 0), word, font=font)
        word_w = word_bbox[2] - word_bbox[0]
        needed = word_w + (space_width if current_line else 0)

        if current_line and current_width + needed > max_width:
            lines.append(current_line)
            current_line = [(word, is_hl)]
            current_width = word_w
        else:
            current_line.append((word, is_hl))
            current_width += needed

    if current_line:
        lines.append(current_line)

    # Draw each line centered with text shadow for legibility
    shadow_offset = 3
    shadow_color = (0, 0, 0, 200)
    current_y = y
    for line_words in lines:
        # Calculate total line width
        line_text = " ".join(w for w, _ in line_words)
        line_bbox = draw.textbbox((0, 0), line_text, font=font)
        line_w = line_bbox[2] - line_bbox[0]
        line_h = line_bbox[3] - line_bbox[1]

        # Center horizontally
        x = (SLIDE_WIDTH - line_w) // 2

        # Shadow pass
        cursor_x = x
        for j, (word, is_hl) in enumerate(line_words):
            draw.text((cursor_x + shadow_offset, current_y + shadow_offset), word, font=font, fill=shadow_color)
            word_bbox = draw.textbbox((0, 0), word, font=font)
            cursor_x += word_bbox[2] - word_bbox[0] + space_width

        # Color pass
        cursor_x = x
        for j, (word, is_hl) in enumerate(line_words):
            color = highlight_color if is_hl else normal_color
            draw.text((cursor_x, current_y), word, font=font, fill=color)
            word_bbox = draw.textbbox((0, 0), word, font=font)
            cursor_x += word_bbox[2] - word_bbox[0] + space_width

        current_y += int(line_h * line_spacing)

    return current_y


def _draw_profile_circle(img: Image.Image, y_center: int):
    """Draw circular profile picture centered horizontally. No-op if no profile pic exists."""
    if PROFILE_PIC_PATH is None:
        return

    try:
        pic = Image.open(PROFILE_PIC_PATH).convert("RGBA")
        size = 64
        pic = pic.resize((size, size), Image.LANCZOS)

        # Create circular mask
        mask = Image.new("L", (size, size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse([0, 0, size, size], fill=255)

        # Create circular image
        circle = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        circle.paste(pic, (0, 0), mask)

        # Add thin border ring
        border_size = size + 6
        border = Image.new("RGBA", (border_size, border_size), (0, 0, 0, 0))
        border_draw = ImageDraw.Draw(border)
        border_draw.ellipse([0, 0, border_size, border_size], outline=(255, 255, 255, 180), width=2)
        border.paste(circle, (3, 3), circle)

        x = (SLIDE_WIDTH - border_size) // 2
        y = y_center - border_size // 2
        img.paste(border, (x, y), border)
    except Exception as e:
        logger.warning(f"Could not draw profile picture: {e}")


def _draw_slide_counter(draw: ImageDraw.Draw, current: int, total: int):
    """Draw slide counter (e.g., '1/11') in top-right corner with rounded background."""
    font = _get_font(22, bold=True)
    text = f"{current}/{total}"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    # Background pill
    pad_x, pad_y = 14, 8
    rx = SLIDE_WIDTH - tw - pad_x * 2 - 30
    ry = 30
    draw.rounded_rectangle(
        [rx, ry, rx + tw + pad_x * 2, ry + th + pad_y * 2],
        radius=16,
        fill=(0, 0, 0, 140),
    )
    draw.text((rx + pad_x, ry + pad_y), text, font=font, fill=(255, 255, 255, 230))


def _create_cover_slide(
    slide: dict, template: dict, total_slides: int, ai_background: Image.Image | None = None
) -> Image.Image:
    """Create the cover slide with 60/40 layout inspired by top tech IG accounts.

    Layout:
    - Top 60%: AI-generated contextual image (or gradient fallback)
    - Transition: dark gradient overlay fading from transparent to dark
    - Profile picture: small circle centered at transition zone
    - Bottom 40%: title tag (accent) + headline with bicolor highlight + CTA
    """
    img = Image.new("RGBA", (SLIDE_WIDTH, SLIDE_HEIGHT))
    draw = ImageDraw.Draw(img)

    # Zone boundaries
    image_zone_end = int(SLIDE_HEIGHT * 0.55)   # image fills top 55%
    text_zone_start = int(SLIDE_HEIGHT * 0.52)   # text zone begins (with overlap for gradient)

    if ai_background is not None:
        # Place AI image in top zone
        img.paste(ai_background, (0, 0))
        logger.info("Cover slide using AI-generated background")
    else:
        # Fallback: full gradient
        bg = template["background"]
        _draw_gradient(draw, SLIDE_WIDTH, SLIDE_HEIGHT, bg["color_top"], bg["color_bottom"])

    # Dark gradient overlay — must guarantee text legibility
    # Zone 0-35%: light vignette only (image visible)
    # Zone 35-50%: rapid transition to near-opaque (image fades out)
    # Zone 50-100%: solid dark (text zone, fully legible)
    overlay = Image.new("RGBA", (SLIDE_WIDTH, SLIDE_HEIGHT), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    transition_start = int(SLIDE_HEIGHT * 0.32)
    solid_start = int(SLIDE_HEIGHT * 0.50)
    for y in range(SLIDE_HEIGHT):
        if y < transition_start:
            # Top zone: very subtle darkening for vignette feel
            alpha = int(y / transition_start * 30)
        elif y < solid_start:
            # Transition zone: rapid fade from 30 to 245
            progress = (y - transition_start) / (solid_start - transition_start)
            alpha = int(30 + progress * progress * 215)
        else:
            # Text zone: near-opaque black
            alpha = 245
        overlay_draw.line([(0, y), (SLIDE_WIDTH, y)], fill=(5, 8, 18, alpha))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # Profile picture at the transition zone
    profile_y = int(SLIDE_HEIGHT * 0.50)
    _draw_profile_circle(img, profile_y)
    draw = ImageDraw.Draw(img)  # refresh after paste

    # Slide counter (1/N) in top-right
    _draw_slide_counter(draw, 1, total_slides)

    px = LAYOUT["padding_x"]
    max_w = SLIDE_WIDTH - 2 * px

    # === TITLE TAG (short hook in accent color, centered) ===
    title_text = slide.get("title", "").upper()
    title_font = _get_font(FONT_SIZES["cover_title"], bold=True)
    title_y = int(SLIDE_HEIGHT * 0.56)

    # Center the title tag
    title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
    title_w = title_bbox[2] - title_bbox[0]

    # Draw title with shadow for legibility
    shadow_color = (0, 0, 0, 200)
    if title_w > max_w:
        # Shadow
        _draw_text_wrapped(
            draw, title_text,
            (SLIDE_WIDTH - max_w) // 2 + 3, title_y + 3, max_w,
            title_font, shadow_color, line_spacing=1.2,
        )
        title_y = _draw_text_wrapped(
            draw, title_text,
            (SLIDE_WIDTH - max_w) // 2, title_y, max_w,
            title_font, template["accent_color"], line_spacing=1.2,
        )
    else:
        title_x = (SLIDE_WIDTH - title_w) // 2
        draw.text((title_x + 3, title_y + 3), title_text, font=title_font, fill=shadow_color)
        draw.text((title_x, title_y), title_text, font=title_font, fill=template["accent_color"])
        title_y += title_bbox[3] - title_bbox[1] + 10

    # === SUBTITLE / HEADLINE (bicolor: white + accent highlights, centered) ===
    subtitle_text = slide.get("subtitle", "")
    if subtitle_text:
        subtitle_text = subtitle_text.upper()
        subtitle_font = _get_font(52, bold=True)
        subtitle_y = title_y + 15

        end_y = _draw_bicolor_text_centered(
            draw, subtitle_text, subtitle_y, max_w,
            subtitle_font, template["title_color"], template["accent_color"],
        )
    else:
        end_y = title_y

    # === CTA: "DESLIZA PARA CONOCER TODOS LOS DETALLES" ===
    cta_font = _get_font(20, bold=True)
    cta_text = "-DESLIZA PARA CONOCER TODOS LOS DETALLES-"
    cta_bbox = draw.textbbox((0, 0), cta_text, font=cta_font)
    cta_w = cta_bbox[2] - cta_bbox[0]
    cta_x = (SLIDE_WIDTH - cta_w) // 2
    cta_y = int(SLIDE_HEIGHT * 0.93)
    draw.text((cta_x, cta_y), cta_text, font=cta_font, fill=template["accent_color"])

    return img


def _apply_darkened_background(img: Image.Image, draw: ImageDraw.Draw, template: dict, ai_bg: Image.Image | None):
    """Apply AI background heavily darkened, or fall back to gradient."""
    bg = template["background"]
    _draw_gradient(draw, SLIDE_WIDTH, SLIDE_HEIGHT, bg["color_top"], bg["color_bottom"])

    if ai_bg is not None:
        # Composite the AI image with heavy darkening (opacity ~20-25%)
        dark_overlay = Image.new("RGBA", (SLIDE_WIDTH, SLIDE_HEIGHT), (0, 0, 0, 0))
        dark_overlay.paste(ai_bg, (0, 0))
        # Reduce opacity to ~22% so it's a subtle texture
        alpha = dark_overlay.split()[3]
        alpha = alpha.point(lambda p: int(p * 0.22))
        dark_overlay.putalpha(alpha)
        composite = Image.alpha_composite(img, dark_overlay)
        img.paste(composite)


def _create_content_slide(
    slide: dict, template: dict, slide_index: int, total_slides: int,
    ai_background: Image.Image | None = None,
) -> Image.Image:
    """Create a content slide with title + body text."""
    img = Image.new("RGBA", (SLIDE_WIDTH, SLIDE_HEIGHT))
    draw = ImageDraw.Draw(img)

    _apply_darkened_background(img, draw, template, ai_background)

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

    # Title (with highlight support)
    title_font = _get_font(FONT_SIZES["slide_title"], bold=True)
    title_y = int(SLIDE_HEIGHT * LAYOUT["title_y"])
    end_y = _draw_text_wrapped(
        draw, slide.get("title", ""), px, title_y, max_w,
        title_font, template["title_color"],
        highlight_color=template["accent_color"],
    )

    # Accent line
    _draw_accent_line(draw, template, end_y + 15)

    # Body text (with highlight support)
    body_font = _get_font(FONT_SIZES["slide_body"])
    body_y = end_y + 45
    _draw_text_wrapped(
        draw, slide.get("body", ""), px, body_y, max_w,
        body_font, template["body_color"], line_spacing=LAYOUT["line_spacing"],
        highlight_color=template["accent_color"],
    )

    # Progress dots
    _draw_progress_dots(draw, slide_index, total_slides, template)

    _draw_branded_footer(img, draw, template)
    return img


def _create_cta_slide(
    slide: dict, template: dict, total_slides: int,
    ai_background: Image.Image | None = None,
) -> Image.Image:
    """Create the call-to-action slide."""
    img = Image.new("RGBA", (SLIDE_WIDTH, SLIDE_HEIGHT))
    draw = ImageDraw.Draw(img)

    _apply_darkened_background(img, draw, template, ai_background)

    px = LAYOUT["padding_x"]
    max_w = SLIDE_WIDTH - 2 * px

    # CTA title (with highlight support)
    title_font = _get_font(FONT_SIZES["cta_title"], bold=True)
    title_y = int(SLIDE_HEIGHT * 0.30)
    end_y = _draw_text_wrapped(
        draw, slide.get("title", ""), px, title_y, max_w,
        title_font, template["accent_color"],
        highlight_color=template["title_color"],
    )

    # Accent line
    _draw_accent_line(draw, template, end_y + 20)

    # CTA body (with highlight support)
    body_font = _get_font(FONT_SIZES["cta_body"])
    body_y = end_y + 55
    _draw_text_wrapped(
        draw, slide.get("body", ""), px, body_y, max_w,
        body_font, template["body_color"], line_spacing=1.6,
        highlight_color=template["accent_color"],
    )

    # Handle prominent (bigger, centered, branded)
    handle_font = _get_font(44, bold=True)
    bbox = draw.textbbox((0, 0), INSTAGRAM_HANDLE, font=handle_font)
    hw = bbox[2] - bbox[0]
    handle_y = int(SLIDE_HEIGHT * 0.73)
    handle_x = (SLIDE_WIDTH - hw) // 2

    # Accent underline under handle
    draw.rectangle(
        [handle_x, handle_y + (bbox[3] - bbox[1]) + 8,
         handle_x + hw, handle_y + (bbox[3] - bbox[1]) + 12],
        fill=template["accent_color"],
    )
    draw.text(
        (handle_x, handle_y),
        INSTAGRAM_HANDLE,
        font=handle_font,
        fill=template["title_color"],
    )

    _draw_progress_dots(draw, total_slides - 1, total_slides, template)
    _draw_branded_footer(img, draw, template)
    return img


# ── Main Entry Point ────────────────────────────────────────────────────────

def create(content: dict, template_index: int | None = None, topic: dict | None = None) -> list[Path]:
    """
    Create all carousel slide images.

    Args:
        content: dict from content_generator with 'slides' key
        template_index: optional index to force a specific template
        topic: optional topic dict for AI cover background generation

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

    # Try to generate AI backgrounds
    ai_cover_bg = None
    ai_content_bg = None
    if topic:
        try:
            cover_slide = next((s for s in slides if s.get("type") == "cover"), None)
            cover_text = cover_slide.get("title", "") if cover_slide else ""

            from modules.prompt_director import PromptDirector
            director = PromptDirector()
            image_prompt = director.craft_cover_image_prompt(topic, cover_text, template)

            if image_prompt:
                from modules.image_generator import generate_cover_background
                ai_cover_bg = generate_cover_background(image_prompt)

            if ai_cover_bg:
                logger.info("AI cover background ready")
            else:
                logger.info("AI cover background unavailable, using gradient fallback")
        except Exception as e:
            logger.warning(f"AI cover background generation failed: {e}")

        # Generate shared content/CTA background
        try:
            from modules.image_generator import generate_content_background
            topic_en = topic.get("topic_en", topic.get("topic", "technology"))
            ai_content_bg = generate_content_background(topic_en)
            if ai_content_bg:
                logger.info("AI content background ready")
            else:
                logger.info("AI content background unavailable, using gradient fallback")
        except Exception as e:
            logger.warning(f"AI content background generation failed: {e}")

    # Clear previous output
    for f in OUTPUT_DIR.glob("slide_*.png"):
        f.unlink()

    image_paths = []
    for i, slide in enumerate(slides):
        slide_type = slide.get("type", "content")

        if slide_type == "cover":
            img = _create_cover_slide(slide, template, total, ai_background=ai_cover_bg)
        elif slide_type == "cta":
            img = _create_cta_slide(slide, template, total, ai_background=ai_content_bg)
        else:
            img = _create_content_slide(slide, template, i, total, ai_background=ai_content_bg)

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
