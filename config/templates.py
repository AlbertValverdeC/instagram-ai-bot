"""
Carousel visual templates.

Each template defines colors, fonts, and layout for the carousel slides.
The system rotates between templates for visual variety.
"""

TEMPLATES = [
    {
        "name": "dark_blue",
        "background": {
            "type": "gradient",
            "color_top": (10, 15, 40),
            "color_bottom": (25, 55, 109),
        },
        "title_color": (255, 255, 255),
        "body_color": (220, 225, 240),
        "accent_color": (0, 200, 255),
        "slide_number_color": (0, 200, 255),
        "watermark_color": (255, 255, 255, 80),
    },
    {
        "name": "dark_purple",
        "background": {
            "type": "gradient",
            "color_top": (20, 5, 35),
            "color_bottom": (75, 20, 120),
        },
        "title_color": (255, 255, 255),
        "body_color": (230, 220, 245),
        "accent_color": (200, 100, 255),
        "slide_number_color": (200, 100, 255),
        "watermark_color": (255, 255, 255, 80),
    },
    {
        "name": "dark_green",
        "background": {
            "type": "gradient",
            "color_top": (5, 20, 15),
            "color_bottom": (15, 80, 60),
        },
        "title_color": (255, 255, 255),
        "body_color": (215, 240, 230),
        "accent_color": (0, 230, 150),
        "slide_number_color": (0, 230, 150),
        "watermark_color": (255, 255, 255, 80),
    },
    {
        "name": "midnight",
        "background": {
            "type": "gradient",
            "color_top": (15, 15, 25),
            "color_bottom": (40, 40, 70),
        },
        "title_color": (255, 255, 255),
        "body_color": (200, 200, 220),
        "accent_color": (255, 180, 50),
        "slide_number_color": (255, 180, 50),
        "watermark_color": (255, 255, 255, 80),
    },
]

# Font sizes (will be scaled relative to slide dimensions)
FONT_SIZES = {
    "cover_title": 72,
    "cover_subtitle": 36,
    "slide_title": 48,
    "slide_body": 38,
    "slide_number": 28,
    "cta_title": 56,
    "cta_body": 36,
    "watermark": 24,
}

# Layout positions (as fractions of slide dimensions)
LAYOUT = {
    "padding_x": 80,           # horizontal padding in pixels
    "padding_top": 160,        # top padding
    "padding_bottom": 120,     # bottom padding
    "title_y": 0.15,           # title Y position as fraction of height
    "body_y": 0.35,            # body text start Y
    "slide_number_y": 0.08,    # slide number Y
    "watermark_y": 0.94,       # watermark Y
    "accent_line_y": 0.28,     # decorative accent line Y
    "accent_line_width": 120,  # accent line width in pixels
    "accent_line_height": 4,   # accent line height in pixels
    "line_spacing": 1.5,       # line spacing multiplier
}
