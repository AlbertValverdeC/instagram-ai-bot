"""
Image generator module: creates AI-generated backgrounds with Google GenAI models or xAI Grok.

Supports providers controlled by IMAGE_PROVIDER env var:
- "google" (default): Imagen / Gemini image models via Google GenAI
- "xai": xAI Grok via OpenAI-compatible API

Returns None on failure so callers can fall back to local gradient backgrounds.
"""

import base64
import io
import logging
import re

from config.settings import (
    GOOGLE_AI_API_KEY,
    GOOGLE_IMAGE_MODEL,
    IMAGE_PROVIDER,
    SLIDE_HEIGHT,
    SLIDE_WIDTH,
    XAI_API_KEY,
    XAI_IMAGE_MODEL,
)
from modules.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

_client = None
_xai_client = None

# Generic fallback prompt when the Director's prompt gets filtered (editable via dashboard)
_DEFAULT_IMAGE_FALLBACK = (
    "Ilustración editorial minimalista dibujada a mano para la marca TechTokio ⚡ 30s, estilo Neo-Tokio nocturno. "
    "Composición simple con UN sujeto principal claro y máximo dos elementos secundarios. "
    "Paleta de marca: carbón oscuro, blanco y azul eléctrico como acento. "
    "El sujeto debe dominar la mitad superior; el 45% inferior oscuro y limpio para texto. "
    "Sin metáforas abstractas, sin escenas complejas, sin texto, sin letras, sin logos."
)

_MODEL_FALLBACKS = (
    "gemini-2.5-flash-image",
    "imagen-4.0-ultra-generate-001",
    "imagen-4.0-generate-001",
)


_STOPWORDS = {
    "de",
    "la",
    "el",
    "los",
    "las",
    "y",
    "en",
    "del",
    "un",
    "una",
    "por",
    "con",
    "para",
    "que",
    "a",
    "al",
    "se",
    "es",
    "su",
    "sus",
    "como",
    "sobre",
    "tema",
    "noticia",
    "the",
    "and",
    "of",
    "to",
    "in",
    "for",
    "on",
    "with",
    "at",
    "is",
    "are",
    "new",
}


def _normalize_topic_label(text: str, max_len: int = 90) -> str:
    """Clean topic string for prompt constraints."""
    topic = " ".join(str(text or "").split()).strip(" ,.;:")
    if not topic:
        return "tecnología"
    return topic[:max_len]


def _extract_keywords(text: str, limit: int = 6) -> list[str]:
    """Extract lightweight topical keywords for stricter visual alignment."""
    words = re.findall(r"[A-Za-zÀ-ÿ0-9]+", str(text or "").lower())
    out = []
    seen = set()
    for w in words:
        if len(w) < 3 or w in _STOPWORDS or w.isdigit():
            continue
        if w in seen:
            continue
        seen.add(w)
        out.append(w)
        if len(out) >= limit:
            break
    return out


def _compose_cover_prompt(base_prompt: str, topic_hint: str | None) -> str:
    """Append hard constraints so cover images stay simple and on-topic."""
    topic = _normalize_topic_label(topic_hint or "")
    keywords = _extract_keywords(topic, limit=5)
    anchors = ", ".join(keywords) if keywords else topic
    hard_rules = (
        f"INSTRUCCIONES OBLIGATORIAS: tema literal '{topic}'. "
        "Ilustración editorial simple hecha a mano. "
        "Composición mínima: 1 sujeto principal claramente relacionado con el tema + máximo 2 elementos secundarios. "
        f"Anclas visuales ligadas al tema: {anchors}. "
        "Evita metáforas abstractas, multitudes, oficinas genéricas y escenas recargadas. "
        "Sujeto en la mitad superior, 45% inferior oscuro y limpio para texto. "
        "Sin texto, sin letras, sin logos."
    )
    return f"{base_prompt.strip()}\n\n{hard_rules}"


def _compose_content_prompt(topic: str, key_points: list[str]) -> str:
    """Create a simple, literal prompt for shared content background."""
    topic_label = _normalize_topic_label(topic)
    keywords = _extract_keywords(topic_label, limit=4)
    for kp in key_points[:6]:
        for kw in _extract_keywords(kp, limit=2):
            if kw not in keywords:
                keywords.append(kw)
            if len(keywords) >= 6:
                break
        if len(keywords) >= 6:
            break
    anchors = ", ".join(keywords[:4]) if keywords else topic_label
    return (
        f"Ilustración editorial minimalista hecha a mano sobre '{topic_label}'. "
        "Diseño simple y limpio: un elemento principal claramente conectado con el tema y, como máximo, dos apoyos visuales. "
        f"Anclas visuales del tema: {anchors}. "
        "Fondo oscuro limpio, contraste alto, textura de tinta/pincel visible, sin fotorealismo. "
        "Evita metáforas abstractas y escenas complejas. Sin texto, sin letras, sin logos."
    )


# ---------------------------------------------------------------------------
# Google GenAI provider (Imagen + Gemini)
# ---------------------------------------------------------------------------


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


def _is_gemini_image_model(model: str) -> bool:
    """Detect Gemini image-generation model IDs."""
    normalized = (model or "").strip().lower()
    return normalized.startswith("gemini-") and "image" in normalized


def _candidate_models() -> list[str]:
    """Ordered list of models to try, beginning with configured model."""
    candidates = []
    seen = set()
    for model in (GOOGLE_IMAGE_MODEL, *_MODEL_FALLBACKS):
        model = (model or "").strip()
        if not model or model in seen:
            continue
        seen.add(model)
        candidates.append(model)
    return candidates


def _image_from_bytes(image_bytes: bytes):
    """Convert image bytes to RGBA PIL image, crop-to-fill then resize to slide dimensions."""
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes))
    img = img.convert("RGBA")

    # Crop to target aspect ratio (center crop) to avoid stretching
    src_w, src_h = img.size
    target_ratio = SLIDE_WIDTH / SLIDE_HEIGHT  # 1080/1350 = 0.8

    if src_w / src_h > target_ratio:
        # Source is wider: crop sides
        new_w = int(src_h * target_ratio)
        offset = (src_w - new_w) // 2
        img = img.crop((offset, 0, offset + new_w, src_h))
    elif src_w / src_h < target_ratio:
        # Source is taller: crop bottom (keep top where subject is)
        new_h = int(src_w / target_ratio)
        img = img.crop((0, 0, src_w, new_h))

    return img.resize((SLIDE_WIDTH, SLIDE_HEIGHT), Image.LANCZOS)


def _generate_with_imagen(client, model: str, prompt: str, aspect_ratio: str):
    """Generate image bytes using Imagen family models."""
    from google.genai import types

    response = client.models.generate_images(
        model=model,
        prompt=prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1,
            aspect_ratio=aspect_ratio,
        ),
    )

    if not getattr(response, "generated_images", None):
        return None

    image_bytes = response.generated_images[0].image.image_bytes
    if not image_bytes:
        return None
    return _image_from_bytes(image_bytes)


def _extract_inline_image_bytes(response) -> bytes | None:
    """Extract first inline image bytes from Gemini generate_content response."""
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            inline_data = getattr(part, "inline_data", None)
            if inline_data is None:
                continue
            data = getattr(inline_data, "data", None)
            if not data:
                continue
            if isinstance(data, str):
                return base64.b64decode(data)
            return data
    return None


def _generate_with_gemini(client, model: str, prompt: str):
    """Generate image bytes using Gemini image-generation models."""
    from google.genai import types

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
        ),
    )
    image_bytes = _extract_inline_image_bytes(response)
    if not image_bytes:
        return None
    return _image_from_bytes(image_bytes)


def _generate_image(client, model: str, prompt: str, aspect_ratio: str):
    """Call the right API for the model family and return PIL image or None."""
    if _is_gemini_image_model(model):
        return _generate_with_gemini(client, model, prompt)
    return _generate_with_imagen(client, model, prompt, aspect_ratio)


def _generate_with_model_fallbacks(client, prompt: str, aspect_ratio: str):
    """Try configured model first, then known fallbacks."""
    last_error = None
    for model in _candidate_models():
        try:
            logger.info(f"Trying image model: {model}")
            img = _generate_image(client, model, prompt, aspect_ratio)
            if img is not None:
                logger.info(f"Image generated with model: {model}")
                return img
            logger.warning(f"Model '{model}' returned no image")
        except Exception as e:
            last_error = e
            logger.warning(f"Model '{model}' failed: {e}")

    if last_error:
        logger.warning(f"All image model attempts failed. Last error: {last_error}")
    return None


# ---------------------------------------------------------------------------
# xAI Grok provider
# ---------------------------------------------------------------------------


def _get_xai_client():
    """Lazy-initialize the xAI client (OpenAI-compatible)."""
    global _xai_client
    if _xai_client is not None:
        return _xai_client

    if not XAI_API_KEY:
        logger.info("XAI_API_KEY not set, xAI image generation disabled")
        return None

    try:
        from openai import OpenAI

        _xai_client = OpenAI(base_url="https://api.x.ai/v1", api_key=XAI_API_KEY)
        return _xai_client
    except ImportError:
        logger.warning("openai package not installed, xAI image generation disabled")
        return None
    except Exception as e:
        logger.warning(f"Failed to initialize xAI client: {e}")
        return None


_NO_TEXT_SUFFIX = (
    " CRITICAL: The image must contain absolutely NO text, NO letters, NO words, "
    "NO numbers, NO watermarks, NO labels, NO captions, NO signatures anywhere in the image."
)


def _generate_with_xai(prompt: str):
    """Call xAI Grok image API and return PIL Image or None."""
    client = _get_xai_client()
    if client is None:
        return None

    # Append hard no-text constraint to every prompt
    safe_prompt = prompt.rstrip() + _NO_TEXT_SUFFIX

    response = client.images.generate(
        model=XAI_IMAGE_MODEL,
        prompt=safe_prompt,
        n=1,
        response_format="b64_json",
        extra_body={"aspect_ratio": "3:4"},
    )

    if not response.data:
        return None

    image_bytes = base64.b64decode(response.data[0].b64_json)
    return _image_from_bytes(image_bytes)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_cover_background(prompt: str, topic_hint: str | None = None, aspect_ratio: str = "3:4"):
    """
    Generate an AI background image for the cover.

    Routes to xAI Grok or Google GenAI based on IMAGE_PROVIDER.
    Tries the Director prompt first, then retries with a safe fallback prompt.
    Returns PIL.Image.Image or None.
    """
    fallback = load_prompt("image_fallback", _DEFAULT_IMAGE_FALLBACK)

    # --- xAI Grok provider ---
    if IMAGE_PROVIDER == "xai":
        try:
            logger.info(f"Generating AI cover background with xAI ({XAI_IMAGE_MODEL})...")
            logger.info(f"Image prompt: {prompt[:150]}...")

            img = _generate_with_xai(prompt)
            if img is not None:
                logger.info(f"xAI cover background generated ({SLIDE_WIDTH}x{SLIDE_HEIGHT})")
                return img

            logger.warning("xAI returned no images. Retrying with fallback prompt...")
            img = _generate_with_xai(fallback)
            if img is not None:
                logger.info(f"xAI cover background generated with fallback ({SLIDE_WIDTH}x{SLIDE_HEIGHT})")
                return img

            logger.warning("xAI fallback also returned no images")
            return None

        except Exception as e:
            logger.warning(f"xAI image generation failed: {e}")
            return None

    # --- Google GenAI provider (default) ---
    client = _get_client()
    if client is None:
        return None

    try:
        final_prompt = _compose_cover_prompt(prompt, topic_hint)
        logger.info(f"Generating AI cover background (configured model: {GOOGLE_IMAGE_MODEL})...")
        logger.info(f"Image prompt: {final_prompt[:200]}...")

        img = _generate_with_model_fallbacks(client, final_prompt, aspect_ratio)
        if img is not None:
            logger.info(f"AI cover background generated ({SLIDE_WIDTH}x{SLIDE_HEIGHT})")
            return img

        logger.warning("No image returned for director prompt. Retrying with fallback prompt...")
        fallback_prompt = _compose_cover_prompt(fallback, topic_hint)
        img = _generate_with_model_fallbacks(client, fallback_prompt, aspect_ratio)
        if img is not None:
            logger.info(f"AI cover background generated with fallback prompt ({SLIDE_WIDTH}x{SLIDE_HEIGHT})")
            return img

        logger.warning("Fallback prompt also returned no images")
        return None

    except Exception as e:
        logger.warning(f"AI image generation failed: {e}")
        return None


def generate_content_background(topic_en: str | dict, aspect_ratio: str = "3:4"):
    """
    Generate a shared AI background for content/CTA slides.

    Style is consistently hand-drawn editorial illustration with thematic relevance.
    Returns PIL.Image.Image or None.
    """
    if isinstance(topic_en, dict):
        topic_label = topic_en.get("topic_en", topic_en.get("topic", "technology"))
        key_points = [str(x) for x in topic_en.get("key_points", []) if str(x).strip()]
    else:
        topic_label = str(topic_en)
        key_points = []

    prompt = _compose_content_prompt(topic_label, key_points)

    # --- xAI Grok provider ---
    if IMAGE_PROVIDER == "xai":
        try:
            logger.info("Generating AI content background with xAI...")
            img = _generate_with_xai(prompt)
            if img is not None:
                logger.info(f"xAI content background generated ({SLIDE_WIDTH}x{SLIDE_HEIGHT})")
                return img

            logger.warning("xAI content background filtered. Trying fallback...")
            fallback_prompt = _compose_content_prompt(topic_label, [])
            img = _generate_with_xai(fallback_prompt)
            if img is not None:
                logger.info("xAI content background generated with fallback")
                return img

            return None

        except Exception as e:
            logger.warning(f"xAI content background generation failed: {e}")
            return None

    # --- Google GenAI provider (default) ---
    client = _get_client()
    if client is None:
        return None

    try:
        logger.info("Generating AI content background...")
        img = _generate_with_model_fallbacks(client, prompt, aspect_ratio)
        if img is not None:
            logger.info(f"AI content background generated ({SLIDE_WIDTH}x{SLIDE_HEIGHT})")
            return img

        logger.warning("Content background filtered. Trying fallback...")
        fallback_prompt = _compose_content_prompt(topic_label, [])
        img = _generate_with_model_fallbacks(client, fallback_prompt, aspect_ratio)
        if img is not None:
            logger.info("AI content background generated with fallback")
            return img
        return None

    except Exception as e:
        logger.warning(f"AI content background generation failed: {e}")
        return None
