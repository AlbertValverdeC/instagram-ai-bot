"""
Content generation module: creates carousel text content using OpenAI.

Generates:
  - Cover slide (hook title + subtitle)
  - 6 content slides (one key point each, texto explicativo con contexto)
  - CTA slide (call-to-action)
  - Instagram caption (with storytelling structure)
  - Alt text for accessibility
"""

import json
import logging
import re

from openai import OpenAI

from config.settings import (
    CONTENT_USE_DIRECTOR,
    NUM_CONTENT_SLIDES,
    OPENAI_API_KEY,
    OPENAI_MODEL,
)
from modules.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


# ── Default fallback prompt (editable via dashboard) ─────────────────────────

_DEFAULT_CONTENT_FALLBACK = """Eres editor/a de carruseles para la marca de Instagram "TechTokio ⚡ 30s".

IDENTIDAD DE MARCA:
- Aura Neo-Tokio: informativo, nocturno, moderno.
- Tono: directo, afilado, con humor inteligente, cero humo.
- Promesa: "entérate antes, entiéndelo fácil, guárdalo para usarlo mañana".

TOPIC: {topic}
KEY POINTS: {key_points}
CONTEXT: {context}

Genera exactamente {total_slides} slides (1 cover + {num_content_slides} contenido + 1 CTA).

OBJETIVO:
- Resumir de forma fiel la noticia y sus puntos clave.
- Aportar valor en cada slide para que se entienda sin leer el artículo completo.

REGLAS:
- No inventes datos ni contexto fuera de KEY POINTS/CONTEXT.
- Mantén el alcance exacto de la noticia; no la sobredimensiones.
- Cada slide de contenido corresponde al key point del mismo orden.
- Cada slide de contenido: entre 38 y 65 palabras.
- Evita bodies tipo titular de una sola línea.
- Cada body debe desarrollar la idea con profundidad real:
  - hecho concreto del tema,
  - contexto para entenderlo,
  - implicación práctica o consecuencia.
- Prohibido usar muletillas/plantillas tipo "Por qué importa:", "Dato clave:".
- Si aplica, usa 2 bloques cortos separados por salto de línea para mejorar lectura.
- Cover:
  - title: 3-5 palabras, contundente y clickbait.
  - subtitle: 12-24 palabras, preciso, con gancho y sin exagerar hechos.
- Resaltados con **:
  - cover subtitle: máximo 2 fragmentos.
  - contenido/CTA: máximo 1 fragmento por campo.
  - cada resaltado: 2-4 palabras.
- Títulos de contenido:
  - Deben ser concretos y entendibles por sí solos.
  - No uses prefijos/etiquetas artificiales ni códigos (ej: RADAR, TOOL, 速報, 判定).
- Body claro y directo; evita relleno.
- CTA orientado a guardar, comentar y seguir.
- Caption: 250-500 caracteres, con hook inicial y pregunta final.
- Incluye el sello de marca "TechTokio ⚡ 30s" una vez (CTA o caption).
- Genera también alt_text y 5 hashtags.

Responde en JSON exacto:
{{
    "slides": [
        {{
            "type": "cover",
            "title": "GANCHO CORTO (3-5 palabras)",
            "subtitle": "TITULAR PRINCIPAL CON **FRASES CLAVE RESALTADAS** EN DOBLE ASTERISCO"
        }},
        {{
            "type": "content",
            "number": 1,
            "title": "Título corto del slide",
            "body": "Texto explicativo con datos"
        }},
        {{
            "type": "content",
            "number": 2,
            "title": "Título corto del slide",
            "body": "Texto explicativo con datos"
        }},
        {{
            "type": "content",
            "number": 3,
            "title": "Título corto del slide",
            "body": "Texto explicativo con datos"
        }},
        {{
            "type": "content",
            "number": 4,
            "title": "Título corto del slide",
            "body": "Texto explicativo con datos"
        }},
        {{
            "type": "content",
            "number": 5,
            "title": "Título corto del slide",
            "body": "Texto explicativo con datos"
        }},
        {{
            "type": "content",
            "number": 6,
            "title": "Título corto del slide",
            "body": "Texto explicativo con datos"
        }},
        {{
            "type": "cta",
            "title": "Titular CTA con urgencia",
            "body": "Mensaje CTA para guardar, compartir y seguir"
        }}
    ],
    "caption": "Caption de Instagram que empieza con un HOOK",
    "alt_text": "Descripción accesible del carrusel",
    "hashtag_suggestions": ["#hashtag1", "#hashtag2", "#hashtag3", "#hashtag4", "#hashtag5"]
}}"""


def _safe_text(value) -> str:
    """Return a stripped string or empty string."""
    if value is None:
        return ""
    return str(value).strip()


def _clean_punctuation_spacing(text: str, keep_newlines: bool = False) -> str:
    """Normalize spacing and avoid isolated punctuation lines (e.g. 'HACER .')."""
    raw = str(text or "")
    if not keep_newlines:
        clean = re.sub(r"\s+", " ", raw).strip()
        clean = re.sub(r"\s+([,.;:!?])", r"\1", clean)
        clean = re.sub(r"([¿¡])\s+", r"\1", clean)
        return clean

    lines = raw.splitlines()
    clean_lines = []
    for line in lines:
        line_clean = re.sub(r"[ \t]+", " ", line).strip()
        line_clean = re.sub(r"\s+([,.;:!?])", r"\1", line_clean)
        line_clean = re.sub(r"([¿¡])\s+", r"\1", line_clean)
        clean_lines.append(line_clean)
    return "\n".join(clean_lines).strip()


def _limit_highlights(text: str, max_segments: int, max_words_per_segment: int) -> str:
    """Limit number/size of **highlighted** segments and strip accidental leftovers."""
    value = str(text or "")
    pattern = re.compile(r"\*\*(.+?)\*\*")
    matches = list(pattern.finditer(value))
    if not matches or max_segments <= 0:
        return value.replace("**", "")

    signal_words = {
        "crisis", "récord", "record", "impacto", "cae", "sube", "lanza", "lanzó",
        "despidos", "empleos", "fmi", "pib", "crecimiento", "inflación", "riesgo",
        "gana", "pierde", "subida", "bajada", "alerta", "urgente",
    }

    def score_phrase(phrase: str) -> int:
        words = phrase.lower().split()
        wc = len(words)
        score = 0
        if any(ch.isdigit() for ch in phrase):
            score += 3
        if 2 <= wc <= 4:
            score += 2
        elif wc > 6:
            score -= 2
        if any(w.strip(".,;:!?") in signal_words for w in words):
            score += 2
        return score

    scored = []
    for idx, m in enumerate(matches):
        phrase = " ".join(m.group(1).split())
        scored.append((score_phrase(phrase), idx))

    scored.sort(key=lambda x: (-x[0], x[1]))
    keep_idx = {idx for _, idx in scored[:max_segments]}
    keep_idx = set(sorted(keep_idx))

    pieces = []
    cursor = 0
    for idx, m in enumerate(pattern.finditer(value)):
        pieces.append(value[cursor:m.start()].replace("**", ""))
        phrase = " ".join(m.group(1).split())
        if idx in keep_idx and phrase:
            words = phrase.split()
            if len(words) <= max_words_per_segment:
                pieces.append(f"**{phrase}**")
            else:
                # Keep wording intact; if too long, remove highlight instead of truncating meaning.
                pieces.append(phrase)
        else:
            pieces.append(phrase)
        cursor = m.end()
    pieces.append(value[cursor:].replace("**", ""))

    clean = "".join(pieces)
    return clean


def _clarify_ambiguous_text(text: str) -> str:
    """Light text cleanup without topic-specific rewrites."""
    clean = str(text or "")
    clean = re.sub(r"[ \t]+", " ", clean).strip()
    return clean


def _tokenize_overlap(text: str) -> set[str]:
    """Lightweight tokenization used to verify factual overlap."""
    return {
        t for t in re.findall(r"[A-Za-zÀ-ÿ0-9]+", str(text or "").lower())
        if len(t) >= 3
    }


_GENERIC_CONTENT_TOKENS = {
    "agentes",
    "agente",
    "ia",
    "inteligencia",
    "artificial",
    "tecnologia",
    "tecnologico",
    "tecnologica",
    "plataforma",
    "sistema",
    "sistemas",
    "social",
    "red",
    "redes",
    "humanos",
    "usuario",
    "usuarios",
    "impacto",
    "debate",
    "debates",
    "etica",
    "legal",
    "legales",
    "futuro",
    "comunidad",
    "mundo",
    "interacciones",
}

_TITLE_STOPWORDS = {
    "el", "la", "los", "las", "de", "del", "un", "una", "y", "en", "con", "para",
    "que", "por", "se", "su", "sus", "como", "más", "mas", "al", "lo", "ya",
    "this", "that", "with", "from", "into", "over", "under", "today",
}

_TITLE_VERB_TOKENS = {
    "es", "son", "fue", "fueron", "será", "serán",
    "puede", "pueden", "podrá", "podrán",
    "ofrece", "ofrecen", "ofreció", "ofrecerá",
    "presenta", "presentan", "presentó",
    "viene", "vienen", "vino",
    "permite", "permiten", "permitió",
    "busca", "buscan", "mejora", "mejora", "mejoran",
    "integra", "integran", "usa", "usan", "tiene", "tienen",
    "interactúa", "interactúan", "interactuar",
}

_TITLE_LABEL_PREFIX_RE = re.compile(
    r"^\s*(?:\[\s*)?(?:速報|判定|radar|tool|alerta|tag|label|etiqueta)\s*(?:\]\s*)?[:\-–—]\s*",
    flags=re.IGNORECASE,
)


def _compact_fact(text: str, max_words: int = 20) -> str:
    words = str(text or "").split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words]) + "..."


def _word_count(text: str) -> int:
    """Count words in text, ignoring punctuation-only tokens."""
    return len(re.findall(r"[A-Za-zÀ-ÿ0-9]+", str(text or "")))


def _title_case_token(token: str) -> str:
    """Keep acronyms as-is and title-case normal tokens."""
    if len(token) <= 4 and token.isupper():
        return token
    if token.isdigit():
        return token
    return token[:1].upper() + token[1:].lower()


def _title_from_key_point(key_point: str, number: int) -> str:
    """Build a concrete short title from the key point when model title is weak."""
    tokens = re.findall(r"[A-Za-zÀ-ÿ0-9]+", str(key_point or ""))
    picked = []
    for tok in tokens:
        low = tok.lower()
        if low in _TITLE_STOPWORDS:
            continue
        if low in _TITLE_VERB_TOKENS:
            continue
        picked.append(_title_case_token(tok))
        if len(picked) >= 5:
            break
    if not picked:
        return f"Clave {number}"
    return " ".join(picked[:4])


def _normalize_content_title(title: str, key_point: str, number: int) -> str:
    """
    Remove artificial label prefixes and guarantee a meaningful title.
    """
    clean = _safe_text(title)
    # Remove repeated label-like prefixes (e.g. "RADAR: ...", "速報: ...")
    while True:
        updated = _TITLE_LABEL_PREFIX_RE.sub("", clean).strip()
        if updated == clean:
            break
        clean = updated

    generic_patterns = (
        r"^punto\s+clave\b",
        r"^slide\s+\d+\b",
        r"^content\b",
        r"^dato\s+clave\b",
        r"^tema\b",
    )
    if not clean:
        return _title_from_key_point(key_point, number)
    if any(re.search(pat, clean, flags=re.IGNORECASE) for pat in generic_patterns):
        return _title_from_key_point(key_point, number)

    # If title is too short and vague, rebuild from key point.
    if _word_count(clean) <= 2 and _word_count(key_point) >= 6:
        return _title_from_key_point(key_point, number)
    # If title is too sentence-like (verb-heavy), rebuild as noun phrase.
    title_tokens = [t.lower() for t in re.findall(r"[A-Za-zÀ-ÿ0-9]+", clean)]
    verb_hits = sum(1 for t in title_tokens if t in _TITLE_VERB_TOKENS)
    if verb_hits >= 1 and len(title_tokens) >= 4:
        return _title_from_key_point(key_point, number)
    return clean


def _ensure_body_grounded(body: str, key_point: str) -> str:
    """
    Ensure each slide body includes at least one concrete fact grounded in its key point.
    """
    body_clean = str(body or "").strip()
    point_clean = str(key_point or "").strip()
    if not point_clean:
        return body_clean

    body_tokens = _tokenize_overlap(body_clean)
    point_tokens = _tokenize_overlap(point_clean)
    overlap = len(body_tokens.intersection(point_tokens))
    body_specific = {t for t in body_tokens if t not in _GENERIC_CONTENT_TOKENS}
    point_specific = {t for t in point_tokens if t not in _GENERIC_CONTENT_TOKENS}
    overlap_specific = len(body_specific.intersection(point_specific))
    has_number = bool(re.search(r"\d", body_clean))

    if has_number or overlap_specific >= 2 or overlap >= 5:
        return body_clean

    fact = _compact_fact(point_clean, max_words=18)
    if not body_clean:
        return fact
    return f"{body_clean}\n{fact}"


def _has_missing_slide_text(content: dict) -> bool:
    """Return True if any slide misses required text fields."""
    slides = content.get("slides")
    if not isinstance(slides, list) or not slides:
        return True

    for slide in slides:
        if not isinstance(slide, dict):
            return True
        stype = _safe_text(slide.get("type")).lower()
        if stype == "cover":
            if not _safe_text(slide.get("title")) or not _safe_text(slide.get("subtitle")):
                return True
        elif stype == "cta":
            if not _safe_text(slide.get("title")) or not _safe_text(slide.get("body")):
                return True
        else:
            if not _safe_text(slide.get("title")) or not _safe_text(slide.get("body")):
                return True
    return False


def _build_content_fallback_prompt(
    topic_text: str,
    key_points_text: str,
    context_text: str,
    total_slides: int,
    num_content_slides: int,
) -> str:
    """Build deterministic fallback prompt from dashboard template or default."""
    try:
        template = load_prompt("content_fallback", _DEFAULT_CONTENT_FALLBACK)
        return template.format(
            topic=topic_text,
            key_points=key_points_text,
            context=context_text,
            total_slides=total_slides,
            num_content_slides=num_content_slides,
        )
    except (KeyError, IndexError) as e:
        logger.warning(f"Custom content_fallback prompt error: {e}. Using default.")
        return _DEFAULT_CONTENT_FALLBACK.format(
            topic=topic_text,
            key_points=key_points_text,
            context=context_text,
            total_slides=total_slides,
            num_content_slides=num_content_slides,
        )


def _is_viable_director_content_prompt(prompt_text: str) -> bool:
    """
    Basic prompt sanity-check to avoid burning a full generation call on weak prompts.
    """
    text = str(prompt_text or "").strip()
    if not text:
        return False
    if len(text) < 300:
        return False
    low = text.lower()
    required_tokens = (
        "json",
        "slides",
        "caption",
        "alt_text",
        "hashtag_suggestions",
    )
    if any(token not in low for token in required_tokens):
        return False
    if "8 slides" not in low and "exactamente 8" not in low:
        return False
    return True


def _normalize_content(content: dict, topic: dict) -> dict:
    """
    Normalize content to avoid blank slides.

    Output is forced to: 1 cover + NUM_CONTENT_SLIDES content + 1 CTA.
    """
    topic_title = _safe_text(topic.get("topic")) or "ESTE TEMA"
    key_points = [str(x).strip() for x in topic.get("key_points", []) if str(x).strip()]

    slides_in = content.get("slides")
    if not isinstance(slides_in, list):
        slides_in = []

    cover_src = next((s for s in slides_in if isinstance(s, dict) and _safe_text(s.get("type")).lower() == "cover"), {})
    cta_src = next((s for s in slides_in if isinstance(s, dict) and _safe_text(s.get("type")).lower() == "cta"), {})
    content_src = [
        s for s in slides_in
        if isinstance(s, dict) and _safe_text(s.get("type")).lower() not in ("cover", "cta")
    ]

    repaired_slides = []

    # Cover
    cover_title = _safe_text(cover_src.get("title")) or "ACTUALIDAD TECH"
    cover_title = _clarify_ambiguous_text(cover_title)
    cover_title = _clean_punctuation_spacing(cover_title)
    cover_subtitle = _safe_text(cover_src.get("subtitle")) or f"LO MÁS IMPORTANTE SOBRE **{topic_title.upper()}** EN 60 SEGUNDOS"
    cover_subtitle = _clarify_ambiguous_text(cover_subtitle)
    cover_subtitle = _clean_punctuation_spacing(cover_subtitle)
    cover_subtitle = _limit_highlights(cover_subtitle, max_segments=2, max_words_per_segment=4)
    repaired_slides.append({
        "type": "cover",
        "title": cover_title,
        "subtitle": cover_subtitle,
    })

    # Content slides (fixed count)
    for i in range(NUM_CONTENT_SLIDES):
        src = content_src[i] if i < len(content_src) else {}
        point = key_points[i] if i < len(key_points) else "Dato clave para entender este tema."
        title = _normalize_content_title(_safe_text(src.get("title")), point, i + 1)
        body = _safe_text(src.get("body")) or point
        body = _ensure_body_grounded(body, point)
        title = _clarify_ambiguous_text(title)
        body = _clarify_ambiguous_text(body)
        title = _clean_punctuation_spacing(title)
        body = _clean_punctuation_spacing(body, keep_newlines=True)
        title = _limit_highlights(title, max_segments=1, max_words_per_segment=3)
        body = _limit_highlights(body, max_segments=1, max_words_per_segment=4)
        repaired_slides.append({
            "type": "content",
            "number": i + 1,
            "title": title,
            "body": body,
        })

    # CTA
    cta_title = _safe_text(cta_src.get("title")) or "¿TE HA SERVIDO ESTE RESUMEN?"
    cta_body = _safe_text(cta_src.get("body")) or "GUÁRDALO Y SÍGUEME PARA MÁS ACTUALIDAD DE TECH E IA."
    cta_title = _clarify_ambiguous_text(cta_title)
    cta_body = _clarify_ambiguous_text(cta_body)
    cta_title = _clean_punctuation_spacing(cta_title)
    cta_body = _clean_punctuation_spacing(cta_body, keep_newlines=True)
    cta_title = _limit_highlights(cta_title, max_segments=1, max_words_per_segment=3)
    cta_body = _limit_highlights(cta_body, max_segments=1, max_words_per_segment=4)
    repaired_slides.append({
        "type": "cta",
        "title": cta_title,
        "body": cta_body,
    })

    caption = _safe_text(content.get("caption")) or f"Lo más importante sobre {topic_title} en formato carrusel. ¿Qué opinas?"
    alt_text = _safe_text(content.get("alt_text")) or f"Carrusel informativo sobre {topic_title}."
    hashtags = content.get("hashtag_suggestions")
    if not isinstance(hashtags, list) or len(hashtags) == 0:
        hashtags = ["#tecnologia", "#actualidad", "#economia", "#ia", "#noticias"]
    hashtags = [str(h).strip() for h in hashtags if str(h).strip()][:5]
    if len(hashtags) < 5:
        fallback_tags = ["#tecnologia", "#actualidad", "#economia", "#ia", "#noticias"]
        for tag in fallback_tags:
            if len(hashtags) >= 5:
                break
            if tag not in hashtags:
                hashtags.append(tag)

    return {
        "slides": repaired_slides,
        "caption": caption,
        "alt_text": alt_text,
        "hashtag_suggestions": hashtags,
    }


def _refine_content_titles_with_llm(client: OpenAI, normalized: dict, topic: dict) -> dict:
    """
    Run a lightweight title-polish pass to keep content slide titles natural and meaningful.
    Falls back silently to existing titles on any failure.
    """
    try:
        slides = normalized.get("slides", [])
        content_slides = [s for s in slides if s.get("type") == "content"]
        if len(content_slides) != NUM_CONTENT_SLIDES:
            return normalized

        key_points = [str(x).strip() for x in topic.get("key_points", []) if str(x).strip()]
        current_titles = [str(s.get("title", "")).strip() for s in content_slides]

        payload = {
            "topic": topic.get("topic", ""),
            "key_points": key_points[:NUM_CONTENT_SLIDES],
            "current_titles": current_titles,
        }
        prompt = (
            "Reescribe los 6 títulos de slides de un carrusel en español.\n"
            "Objetivo: títulos naturales, concretos y fáciles de entender.\n"
            "Reglas obligatorias:\n"
            "- Devuelve exactamente 6 títulos en el mismo orden.\n"
            "- Cada título: 2 a 5 palabras.\n"
            "- Formato nominal (evita verbos conjugados y frases raras).\n"
            "- No usar prefijos/etiquetas tipo RADAR, TOOL, 速報, 判定.\n"
            "- No usar comillas, emojis ni dos puntos.\n"
            "- Deben reflejar fielmente cada key point, sin inventar.\n"
            "Responde JSON exacto con esta forma:\n"
            '{"titles":["...","...","...","...","...","..."]}\n\n'
            f"DATOS:\n{json.dumps(payload, ensure_ascii=False)}"
        )

        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
        titles = data.get("titles")
        if not isinstance(titles, list) or len(titles) != NUM_CONTENT_SLIDES:
            return normalized

        polished = [re.sub(r"\s+", " ", str(t or "")).strip() for t in titles]
        if any(not t for t in polished):
            return normalized

        # Apply polished titles back in order.
        idx = 0
        for slide in slides:
            if slide.get("type") == "content":
                slide["title"] = polished[idx]
                idx += 1
        return normalized
    except Exception:
        return normalized


def _refine_content_bodies_with_llm(client: OpenAI, normalized: dict, topic: dict) -> dict:
    """
    Rewrite content bodies for depth and clarity (without repetitive templates).
    Falls back silently if the refinement fails.
    """
    try:
        slides = normalized.get("slides", [])
        content_slides = [s for s in slides if s.get("type") == "content"]
        if len(content_slides) != NUM_CONTENT_SLIDES:
            return normalized

        key_points = [str(x).strip() for x in topic.get("key_points", []) if str(x).strip()]
        bodies = [str(s.get("body", "")).strip() for s in content_slides]
        titles = [str(s.get("title", "")).strip() for s in content_slides]

        payload = {
            "topic": topic.get("topic", ""),
            "context": topic.get("why", ""),
            "key_points": key_points[:NUM_CONTENT_SLIDES],
            "titles": titles,
            "current_bodies": bodies,
        }
        prompt = (
            "Reescribe los 6 textos de body de un carrusel en español para que aporten profundidad real.\n"
            "Objetivo: que al terminar los 6 slides, el lector entienda la noticia sin leer el artículo original.\n"
            "Reglas obligatorias:\n"
            "- Devuelve exactamente 6 bodies en el mismo orden.\n"
            "- Cada body entre 38 y 65 palabras.\n"
            "- Cada body debe incluir: hecho concreto + contexto explicativo + consecuencia/uso práctico.\n"
            "- No inventar datos fuera de key_points/context.\n"
            "- No repetir frases entre slides.\n"
            "- No usar plantillas literales como 'Por qué importa:' o 'Dato clave:'.\n"
            "- Español claro, directo, sin relleno.\n"
            "Responde JSON exacto con esta forma:\n"
            '{"bodies":["...","...","...","...","...","..."]}\n\n'
            f"DATOS:\n{json.dumps(payload, ensure_ascii=False)}"
        )

        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.35,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
        refined = data.get("bodies")
        if not isinstance(refined, list) or len(refined) != NUM_CONTENT_SLIDES:
            return normalized

        clean_refined = []
        for body in refined:
            text = _clean_punctuation_spacing(str(body or ""), keep_newlines=True)
            wc = _word_count(text)
            if wc < 28:
                return normalized
            clean_refined.append(text)

        idx = 0
        for slide in slides:
            if slide.get("type") == "content":
                slide["body"] = clean_refined[idx]
                idx += 1
        return normalized
    except Exception:
        return normalized


def generate(topic: dict) -> dict:
    """
    Generate full carousel content from a topic.

    Args:
        topic: dict with keys 'topic', 'topic_en', 'key_points', 'why'

    Returns:
        dict with keys: slides, caption, alt_text, hashtag_context
    """
    logger.info(f"Generating content for: {topic['topic']}")

    client = OpenAI(api_key=OPENAI_API_KEY)

    # Pre-compute variables for .format()
    total_slides = NUM_CONTENT_SLIDES + 2
    num_content_slides = NUM_CONTENT_SLIDES
    topic_text = topic['topic']
    key_points_text = json.dumps(topic['key_points'], ensure_ascii=False)
    context_text = topic.get('why', '')

    # Build stable fallback prompt first; this remains the default path.
    fallback_prompt = _build_content_fallback_prompt(
        topic_text=topic_text,
        key_points_text=key_points_text,
        context_text=context_text,
        total_slides=total_slides,
        num_content_slides=num_content_slides,
    )

    # Optionally try Prompt Director for an optimized prompt.
    director_prompt = None
    if CONTENT_USE_DIRECTOR:
        try:
            from modules.prompt_director import PromptDirector
            director = PromptDirector()
            candidate = director.craft_content_prompt(topic)
            if _is_viable_director_content_prompt(candidate):
                director_prompt = candidate
                logger.info("Using director-crafted content prompt")
            else:
                logger.warning("Director content prompt rejected by sanity-check. Using fallback prompt.")
        except Exception as e:
            logger.warning(f"Could not use Prompt Director for content: {e}")
    else:
        logger.info("Content director disabled (CONTENT_USE_DIRECTOR=false). Using fallback prompt.")

    prompt = director_prompt or fallback_prompt

    def _call_openai(p, *, temperature: float = 0.45):
        # OpenAI requires the word "json" in messages when using json_object format
        if "json" not in p.lower():
            p += "\n\nRespond in valid JSON format."
        # Two-attempt decode to reduce transient malformed JSON responses.
        temps = [temperature, 0.2]
        last_err = None
        for idx, temp in enumerate(temps, start=1):
            try:
                resp = client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[{"role": "user", "content": p}],
                    temperature=temp,
                    response_format={"type": "json_object"},
                )
                return json.loads(resp.choices[0].message.content)
            except Exception as e:
                last_err = e
                if idx < len(temps):
                    logger.warning(
                        "Content JSON decode/call failed (attempt %d/%d). Retrying with lower temperature.",
                        idx,
                        len(temps),
                    )
        raise last_err

    content = _call_openai(prompt)

    # Validate structure/text — if director prompt produced bad output, retry with hardcoded
    if "slides" not in content or len(content.get("slides", [])) < 3 or _has_missing_slide_text(content):
        if director_prompt:
            logger.warning("Director prompt produced invalid/incomplete content. Retrying with fallback prompt.")
            content = _call_openai(fallback_prompt)
            if "slides" not in content or len(content.get("slides", [])) < 3:
                raise ValueError(f"Invalid content structure: {list(content.keys())}")
        else:
            raise ValueError(f"Invalid content structure: expected slides, got {list(content.keys())}")

    repaired = _normalize_content(content, topic)
    repaired = _refine_content_titles_with_llm(client, repaired, topic)
    repaired = _refine_content_bodies_with_llm(client, repaired, topic)
    if _has_missing_slide_text(content):
        logger.warning("Content had empty slide fields. Applied automatic repair to avoid blank slides.")

    logger.info(f"Generated {len(repaired['slides'])} slides + caption")
    content = repaired
    return content


# ── CLI Test Mode ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    # Test with a sample topic
    sample_topic = {
        "topic": "Nueva función de IA en móviles",
        "topic_en": "New AI feature in smartphones",
        "why": "Actualización reciente con impacto práctico para usuarios",
        "key_points": [
            "La nueva función automatiza tareas cotidianas desde el móvil.",
            "Se despliega primero en dispositivos recientes de gama alta.",
            "Reduce pasos manuales en acciones frecuentes.",
            "Mejora precisión al aprender de patrones de uso.",
            "La industria lo ve como señal de mayor integración de IA en consumo.",
            "Se esperan más apps compatibles en próximas semanas.",
        ],
    }

    print("=" * 60)
    print("CONTENT GENERATOR — Test Mode")
    print("=" * 60)

    content = generate(sample_topic)
    print(f"\nSlides ({len(content['slides'])}):")
    for slide in content["slides"]:
        print(f"\n  [{slide['type'].upper()}] {slide.get('title', '')}")
        if slide.get("body"):
            print(f"  {slide['body']}")
    print(f"\nCaption: {content['caption'][:200]}...")
    print(f"\nAlt text: {content['alt_text']}")
    print(f"\nHashtags: {content.get('hashtag_suggestions', [])}")
