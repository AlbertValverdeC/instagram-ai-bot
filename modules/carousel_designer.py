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
from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import re

from config.settings import (
    BRAND_LOGO_PATH,
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
_BRAND_LOGO_CACHE: dict[int, Image.Image] = {}


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


def _fit_image_cover(img: Image.Image, width: int, height: int) -> Image.Image:
    """Resize + crop image to fully cover a target rectangle."""
    src_w, src_h = img.size
    if src_w <= 0 or src_h <= 0:
        return img.resize((width, height), Image.LANCZOS)

    scale = max(width / src_w, height / src_h)
    new_w = max(1, int(src_w * scale))
    new_h = max(1, int(src_h * scale))
    resized = img.resize((new_w, new_h), Image.LANCZOS)

    left = max(0, (new_w - width) // 2)
    top = max(0, (new_h - height) // 2)
    return resized.crop((left, top, left + width, top + height))


def _draw_image_card(
    img: Image.Image,
    draw: ImageDraw.Draw,
    source: Image.Image,
    x: int,
    y: int,
    width: int,
    height: int,
    border_color: tuple,
):
    """Draw a rounded media card to emulate editorial carousel layouts."""
    radius = 30
    fitted = _fit_image_cover(source, width, height).copy()

    # Slightly darken card image to avoid visual competition with text.
    dark = Image.new("RGBA", (width, height), (0, 0, 0, 48))
    fitted = Image.alpha_composite(fitted.convert("RGBA"), dark)

    mask = Image.new("L", (width, height), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([0, 0, width, height], radius=radius, fill=255)

    card = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    card.paste(fitted, (0, 0), mask)
    img.paste(card, (x, y), card)

    draw.rounded_rectangle(
        [x, y, x + width, y + height],
        radius=radius,
        outline=(*border_color[:3], 170),
        width=2,
    )


def _line_metrics(draw: ImageDraw.Draw, font: ImageFont.FreeTypeFont, line_spacing: float) -> tuple[int, int]:
    """Return stable line height and line step for consistent text rhythm."""
    try:
        ascent, descent = font.getmetrics()
        metric_height = ascent + descent
    except Exception:
        metric_height = 0

    sample_bbox = draw.textbbox((0, 0), "AgÁy", font=font)
    sample_height = sample_bbox[3] - sample_bbox[1]
    line_height = max(metric_height, sample_height, font.size)
    line_step = max(line_height + 2, int(line_height * line_spacing))
    return line_height, line_step


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

    Text wrapped in **double asterisks** renders only in highlight_color.
    Returns the Y position after the last line.
    """
    # Respect manual line breaks: useful for numbered steps and short paragraph rhythm.
    if "\n" in text:
        current_y = y
        parts = text.split("\n")
        for idx, part in enumerate(parts):
            part = part.strip()
            if not part:
                current_y += max(12, int(font.size * 0.45))
                continue

            current_y = _draw_text_wrapped(
                draw, part, x, current_y, max_width, font, fill,
                line_spacing=line_spacing,
                highlight_color=highlight_color,
            )

            # Tiny breathing room between explicit lines.
            if idx < len(parts) - 1 and parts[idx + 1].strip():
                current_y += max(4, int(font.size * 0.12))
        return current_y

    # Strip ** markers if no highlight color — render plain
    if highlight_color is None:
        clean = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        avg_char_width = font.size * 0.55
        chars_per_line = max(1, int(max_width / avg_char_width))
        lines = textwrap.wrap(clean, width=chars_per_line)
        _, line_step = _line_metrics(draw, font, line_spacing)
        current_y = y
        for line in lines:
            draw.text((x, current_y), line, font=font, fill=fill)
            current_y += line_step
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

    # Draw each line left-aligned with highlight color
    _, line_step = _line_metrics(draw, font, line_spacing)
    current_y = y
    for line_words in lines:
        cursor_x = x

        for word, is_hl in line_words:
            color = highlight_color if is_hl else fill
            draw.text((cursor_x, current_y), word, font=font, fill=color)
            word_bbox = draw.textbbox((0, 0), word, font=font)
            word_w = word_bbox[2] - word_bbox[0]

            cursor_x += word_w + space_width

        current_y += line_step

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


def _get_brand_logo(size: int) -> Image.Image | None:
    """Load and cache brand logo resized as RGBA."""
    if BRAND_LOGO_PATH is None:
        return None
    cached = _BRAND_LOGO_CACHE.get(size)
    if cached is not None:
        return cached

    def _remove_border_background(img: Image.Image) -> Image.Image:
        """
        Remove dark border-connected background and keep the logo subject.
        Useful when the source logo comes as flat RGB without transparency.
        """
        rgb = img.convert("RGB")
        w, h = rgb.size
        if w <= 2 or h <= 2:
            return img.convert("RGBA")

        px = rgb.load()
        border_samples = []
        # Sample all border pixels to estimate background color.
        for x in range(w):
            border_samples.append(px[x, 0])
            border_samples.append(px[x, h - 1])
        for y in range(1, h - 1):
            border_samples.append(px[0, y])
            border_samples.append(px[w - 1, y])

        bg_r = sum(c[0] for c in border_samples) / len(border_samples)
        bg_g = sum(c[1] for c in border_samples) / len(border_samples)
        bg_b = sum(c[2] for c in border_samples) / len(border_samples)
        bg_luma = (bg_r * 299 + bg_g * 587 + bg_b * 114) / 1000

        def similar_to_bg(r: int, g: int, b: int) -> bool:
            dist = abs(r - bg_r) + abs(g - bg_g) + abs(b - bg_b)
            luma = (r * 299 + g * 587 + b * 114) / 1000
            # Keep threshold adaptive but conservative to avoid eating bright logo strokes.
            dist_threshold = 65 if bg_luma < 70 else 52
            luma_threshold = 85 if bg_luma < 70 else 95
            return dist <= dist_threshold and luma <= luma_threshold

        visited = bytearray(w * h)
        q: deque[tuple[int, int]] = deque()

        def push_if_bg(x: int, y: int):
            idx = y * w + x
            if visited[idx]:
                return
            r, g, b = px[x, y]
            if similar_to_bg(r, g, b):
                visited[idx] = 1
                q.append((x, y))

        # Seed flood-fill from borders only (background is usually edge-connected).
        for x in range(w):
            push_if_bg(x, 0)
            push_if_bg(x, h - 1)
        for y in range(1, h - 1):
            push_if_bg(0, y)
            push_if_bg(w - 1, y)

        while q:
            x, y = q.popleft()
            if x > 0:
                push_if_bg(x - 1, y)
            if x < w - 1:
                push_if_bg(x + 1, y)
            if y > 0:
                push_if_bg(x, y - 1)
            if y < h - 1:
                push_if_bg(x, y + 1)

        rgba = rgb.convert("RGBA")
        data = list(rgba.getdata())
        for y in range(h):
            row_start = y * w
            for x in range(w):
                idx = row_start + x
                if visited[idx]:
                    r, g, b, _ = data[idx]
                    data[idx] = (r, g, b, 0)
        rgba.putdata(data)

        # Trim transparent margins so the logo occupies more visual area.
        alpha = rgba.getchannel("A")
        bbox = alpha.getbbox()
        if bbox:
            rgba = rgba.crop(bbox)
        return rgba

    try:
        raw = Image.open(BRAND_LOGO_PATH)
        logo = _remove_border_background(raw)
        logo = _fit_image_cover(logo, size, size)
        _BRAND_LOGO_CACHE[size] = logo
        return logo
    except Exception as e:
        logger.warning(f"Could not load brand logo: {e}")
        return None


def _draw_brand_logo_badge(img: Image.Image, draw: ImageDraw.Draw, template: dict):
    """
    Draw a small persistent brand logo badge in the top-left corner.
    No-op if brand logo file is missing.
    """
    logo_size = 108
    pad = 20
    logo = _get_brand_logo(logo_size)
    if logo is None:
        return

    x = pad
    y = pad
    # Place logo as-is (no circle, no ring, no glow).
    img.paste(logo, (x, y), logo)


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
    # Respect manual line breaks for explicit cover composition.
    if "\n" in text:
        current_y = y
        parts = text.split("\n")
        for idx, part in enumerate(parts):
            part = part.strip()
            if not part:
                current_y += max(12, int(font.size * 0.45))
                continue
            current_y = _draw_bicolor_text_centered(
                draw, part, current_y, max_width, font,
                normal_color, highlight_color, line_spacing=line_spacing,
            )
            if idx < len(parts) - 1 and parts[idx + 1].strip():
                current_y += max(4, int(font.size * 0.12))
        return current_y

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
    _, line_step = _line_metrics(draw, font, line_spacing)
    current_y = y
    for line_words in lines:
        # Calculate total line width
        line_text = " ".join(w for w, _ in line_words)
        line_bbox = draw.textbbox((0, 0), line_text, font=font)
        line_w = line_bbox[2] - line_bbox[0]

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

        current_y += line_step

    return current_y


def _estimate_bicolor_line_count(
    draw: ImageDraw.Draw,
    text: str,
    max_width: int,
    font: ImageFont.FreeTypeFont,
) -> int:
    """Estimate wrapped line count for bicolor text to improve cover layout."""
    segments = _parse_bicolor_text(text)
    words = []
    for seg_text, is_hl in segments:
        for w in seg_text.split():
            words.append((w, is_hl))
    if not words:
        return 0

    space_width = draw.textbbox((0, 0), " ", font=font)[2]
    lines = []
    current_line = []
    current_width = 0
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
    return len(lines)


def _estimate_wrapped_line_count(
    draw: ImageDraw.Draw,
    text: str,
    max_width: int,
    font: ImageFont.FreeTypeFont,
) -> int:
    """Estimate wrapped line count for plain text rendered by _draw_text_wrapped."""
    clean = re.sub(r'\*\*(.+?)\*\*', r'\1', str(text or ""))
    if not clean.strip():
        return 0
    if "\n" in clean:
        count = 0
        for part in clean.split("\n"):
            part = part.strip()
            if not part:
                continue
            count += _estimate_wrapped_line_count(draw, part, max_width, font)
        return count

    avg_char_width = max(1.0, font.size * 0.55)
    chars_per_line = max(1, int(max_width / avg_char_width))
    lines = textwrap.wrap(clean, width=chars_per_line)
    return max(1, len(lines))


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
    _draw_brand_logo_badge(img, draw, template)

    px = LAYOUT["padding_x"]
    max_w = SLIDE_WIDTH - 2 * px

    # === Cover text layout with protected CTA zone ===
    title_text = slide.get("title", "").upper()
    subtitle_text = (slide.get("subtitle", "") or "").upper()

    cta_font = _get_font(20, bold=True)
    cta_text = "-DESLIZA PARA CONOCER TODOS LOS DETALLES-"
    cta_bbox = draw.textbbox((0, 0), cta_text, font=cta_font)
    cta_h = cta_bbox[3] - cta_bbox[1]
    cta_y = int(SLIDE_HEIGHT * 0.945)
    # Keep a safe margin above CTA so long headlines never collide with it.
    cta_safe_top = cta_y - 24

    title_size = FONT_SIZES["cover_title"]
    subtitle_size = 52 if subtitle_text else 0
    title_min = 58
    subtitle_min = 36
    block_start_y = int(SLIDE_HEIGHT * 0.56)

    def _estimate_cover_block_height(t_size: int, s_size: int) -> int:
        title_font_local = _get_font(t_size, bold=True)
        title_lines = _estimate_wrapped_line_count(draw, title_text, max_w, title_font_local)
        _, title_step = _line_metrics(draw, title_font_local, 1.2)
        total_h = max(1, title_lines) * title_step

        if subtitle_text and s_size > 0:
            subtitle_font_local = _get_font(s_size, bold=True)
            subtitle_lines = _estimate_bicolor_line_count(draw, subtitle_text, max_w, subtitle_font_local)
            _, subtitle_step = _line_metrics(draw, subtitle_font_local, 1.20)
            total_h += 18 + (max(1, subtitle_lines) * subtitle_step)
        return total_h

    available_h = cta_safe_top - block_start_y
    estimated_h = _estimate_cover_block_height(title_size, subtitle_size)
    while estimated_h > available_h and (subtitle_size > subtitle_min or title_size > title_min):
        if subtitle_text and subtitle_size > subtitle_min:
            subtitle_size -= 2
        elif title_size > title_min:
            title_size -= 2
        estimated_h = _estimate_cover_block_height(title_size, subtitle_size)

    if estimated_h > available_h:
        block_start_y = max(int(SLIDE_HEIGHT * 0.46), cta_safe_top - estimated_h)

    # Center the title tag
    title_font = _get_font(title_size, bold=True)
    title_y = block_start_y
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
    if subtitle_text:
        subtitle_font = _get_font(subtitle_size, bold=True)
        subtitle_y = title_y + 18

        end_y = _draw_bicolor_text_centered(
            draw, subtitle_text, subtitle_y, max_w,
            subtitle_font, template["title_color"], template["accent_color"], line_spacing=1.20,
        )
    else:
        end_y = title_y

    # === CTA: "DESLIZA PARA CONOCER TODOS LOS DETALLES" ===
    cta_y = min(cta_y, SLIDE_HEIGHT - cta_h - 18)
    cta_w = cta_bbox[2] - cta_bbox[0]
    cta_x = (SLIDE_WIDTH - cta_w) // 2
    draw.text((cta_x, cta_y), cta_text, font=cta_font, fill=template["accent_color"])

    return img


def _apply_darkened_background(img: Image.Image, draw: ImageDraw.Draw, template: dict, ai_bg: Image.Image | None):
    """Apply AI background heavily darkened, or fall back to gradient."""
    bg = template["background"]
    if bg.get("type") == "solid":
        draw.rectangle(
            [0, 0, SLIDE_WIDTH, SLIDE_HEIGHT],
            fill=bg.get("color_top", (10, 10, 12)),
        )
    else:
        _draw_gradient(draw, SLIDE_WIDTH, SLIDE_HEIGHT, bg["color_top"], bg["color_bottom"])

    if ai_bg is not None:
        # Composite the AI image as subtle texture.
        dark_overlay = Image.new("RGBA", (SLIDE_WIDTH, SLIDE_HEIGHT), (0, 0, 0, 0))
        dark_overlay.paste(ai_bg, (0, 0))
        if template.get("style") == "editorial_clean":
            opacity = 0.10
        else:
            opacity = 0.22
        alpha = dark_overlay.split()[3]
        alpha = alpha.point(lambda p: int(p * opacity))
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
    editorial_mode = template.get("style") == "editorial_clean"

    # Unified slide counter style (top-right pill): 1/8, 2/8, ...
    _draw_slide_counter(draw, slide_index + 1, total_slides)
    _draw_brand_logo_badge(img, draw, template)

    # Title (with highlight support)
    title_size = FONT_SIZES["slide_title"] + (4 if editorial_mode else 0)
    title_font = _get_font(title_size, bold=True)
    title_y = int(SLIDE_HEIGHT * LAYOUT["title_y"])
    end_y = _draw_text_wrapped(
        draw, slide.get("title", ""), px, title_y, max_w,
        title_font, template["title_color"],
        highlight_color=template["accent_color"],
    )

    # Accent line (disabled in minimalist editorial mode)
    if not editorial_mode:
        _draw_accent_line(draw, template, end_y + 15)

    # Body text (with highlight support)
    body_size = FONT_SIZES["slide_body"] + (2 if editorial_mode else 0)
    body_font = _get_font(body_size)
    body_y = end_y + (34 if editorial_mode else 45)

    if editorial_mode and template.get("content_image_card"):
        # Keep top as text and reserve a rounded visual card in the lower area.
        card_x = px - 6
        card_w = SLIDE_WIDTH - 2 * card_x
        card_h = int(SLIDE_HEIGHT * 0.34)
        card_y = int(SLIDE_HEIGHT * 0.56)
        card_source = ai_background
        if card_source is None:
            # Graceful fallback so editorial layout remains stable without AI image.
            card_source = Image.new("RGBA", (SLIDE_WIDTH, SLIDE_HEIGHT), (16, 22, 40, 255))
            card_draw = ImageDraw.Draw(card_source)
            _draw_gradient(card_draw, SLIDE_WIDTH, SLIDE_HEIGHT, (20, 30, 58), (34, 44, 82))

        _draw_image_card(
            img,
            draw,
            card_source,
            card_x,
            card_y,
            card_w,
            card_h,
            template["accent_color"],
        )

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
    _draw_slide_counter(draw, total_slides, total_slides)
    _draw_brand_logo_badge(img, draw, template)

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
                topic_hint = topic.get("topic_en", topic.get("topic", "technology"))
                ai_cover_bg = generate_cover_background(image_prompt, topic_hint=topic_hint)

            if ai_cover_bg:
                logger.info("AI cover background ready")
            else:
                logger.info("AI cover background unavailable, using gradient fallback")
        except Exception as e:
            logger.warning(f"AI cover background generation failed: {e}")

        # Generate shared content/CTA background
        try:
            from modules.image_generator import generate_content_background
            ai_content_bg = generate_content_background(topic)
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
