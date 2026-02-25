"""
Image generator module: creates AI-generated backgrounds using Google Imagen.

Uses Imagen 4 (imagen-4.0-generate-001) to produce cover slide backgrounds.
Returns None on any failure so the caller can fall back to gradient backgrounds.
"""

import io
import logging

from config.settings import GOOGLE_AI_API_KEY, GOOGLE_IMAGE_MODEL, SLIDE_HEIGHT, SLIDE_WIDTH
from modules.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

_client = None

# Generic fallback prompt when the Director's prompt gets filtered (editable via dashboard)
_DEFAULT_IMAGE_FALLBACK = (
    "Futuristic tech office environment with holographic displays and neon blue lighting, "
    "dramatic cinematic composition, dark moody atmosphere with volumetric light rays, "
    "no people, no text, no letters, abstract technology concept art"
)


def _get_client():
    """Lazy-initialize the Google GenAI client."""
    global _client
    if _client is not None:
        return _client

    if not GOOGLE_AI_API_KEY:
        logger.info("GOOGLE_AI_API_KEY not set, AI image generation disabled")
        return None

    try:
        from google import genai

        _client = genai.Client(api_key=GOOGLE_AI_API_KEY)
        return _client
    except ImportError:
        logger.warning("google-genai package not installed, AI image generation disabled")
        return None
    except Exception as e:
        logger.warning(f"Failed to initialize Google GenAI client: {e}")
        return None


def _generate_image(client, prompt: str, aspect_ratio: str):
    """Call Imagen API and return PIL Image or None."""
    from google.genai import types
    from PIL import Image

    response = client.models.generate_images(
        model=GOOGLE_IMAGE_MODEL,
        prompt=prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1,
            aspect_ratio=aspect_ratio,
        ),
    )

    if not response.generated_images:
        return None

    image_bytes = response.generated_images[0].image.image_bytes
    img = Image.open(io.BytesIO(image_bytes))
    img = img.convert("RGBA")
    img = img.resize((SLIDE_WIDTH, SLIDE_HEIGHT), Image.LANCZOS)
    return img


def generate_cover_background(prompt: str, aspect_ratio: str = "3:4"):
    """
    Generate an AI background image using Imagen 4.

    Tries the Director prompt first. If the safety filter blocks it (returns no images),
    retries with a generic tech-themed fallback prompt.

    Returns:
        PIL.Image.Image in RGBA mode resized to SLIDE_WIDTH x SLIDE_HEIGHT,
        or None if generation fails for any reason.
    """
    client = _get_client()
    if client is None:
        return None

    try:
        logger.info(f"Generating AI cover background with {GOOGLE_IMAGE_MODEL}...")
        logger.info(f"Image prompt: {prompt[:150]}...")

        # Attempt 1: Director's prompt
        img = _generate_image(client, prompt, aspect_ratio)

        if img is not None:
            logger.info(f"AI cover background generated ({SLIDE_WIDTH}x{SLIDE_HEIGHT})")
            return img

        # Attempt 2: Retry with generic fallback (safety filter likely blocked the prompt)
        logger.warning("Imagen returned no images (likely safety filter). Retrying with fallback prompt...")
        fallback = load_prompt("image_fallback", _DEFAULT_IMAGE_FALLBACK)
        img = _generate_image(client, fallback, aspect_ratio)

        if img is not None:
            logger.info(f"AI cover background generated with fallback prompt ({SLIDE_WIDTH}x{SLIDE_HEIGHT})")
            return img

        logger.warning("Imagen fallback also returned no images")
        return None

    except Exception as e:
        logger.warning(f"AI image generation failed: {e}")
        return None


def generate_content_background(topic_en: str, aspect_ratio: str = "3:4"):
    """
    Generate a shared AI background for content/CTA slides.

    Uses a more abstract, subtle prompt so it works well heavily darkened.
    Returns PIL.Image.Image or None.
    """
    client = _get_client()
    if client is None:
        return None

    prompt = (
        f"Abstract, minimal technology concept art inspired by the theme: {topic_en}. "
        "Dark, moody atmosphere with soft glowing light accents and bokeh effects. "
        "Out of focus, dreamlike quality. No text, no people, no logos. "
        "Cinematic color grading, deep shadows, subtle neon highlights."
    )

    try:
        logger.info("Generating AI content background...")
        img = _generate_image(client, prompt, aspect_ratio)

        if img is not None:
            logger.info(f"AI content background generated ({SLIDE_WIDTH}x{SLIDE_HEIGHT})")
            return img

        # Fallback: generic abstract tech
        logger.warning("Content background filtered. Trying fallback...")
        fallback_prompt = (
            "Abstract dark technology background with soft bokeh lights and subtle "
            "geometric patterns, deep blue and purple tones, no text, no people, "
            "minimal and moody, cinematic atmosphere"
        )
        img = _generate_image(client, fallback_prompt, aspect_ratio)
        if img is not None:
            logger.info("AI content background generated with fallback")
            return img

        return None

    except Exception as e:
        logger.warning(f"AI content background generation failed: {e}")
        return None
