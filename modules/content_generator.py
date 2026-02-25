"""
Content generation module: creates carousel text content using OpenAI.

Generates:
  - Cover slide (hook title + subtitle)
  - 6 content slides (one key point each, concise text)
  - CTA slide (call-to-action)
  - Instagram caption (with storytelling structure)
  - Alt text for accessibility
"""

import json
import logging
import re

from openai import OpenAI

from config.settings import (
    NUM_CONTENT_SLIDES,
    OPENAI_API_KEY,
    OPENAI_MODEL,
)
from modules.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


# ── Default fallback prompt (editable via dashboard) ─────────────────────────

_DEFAULT_CONTENT_FALLBACK = """Eres creador/a de contenido VIRAL para una cuenta de Instagram en español sobre Tech/IA.
Crea un carrusel IRRESISTIBLE sobre el siguiente tema.

TOPIC: {topic}
KEY POINTS: {key_points}
CONTEXT: {context}

Genera un carrusel con exactamente {total_slides} slides (1 cover + {num_content_slides} contenido + 1 CTA).

FORMATO DEL COVER (muy importante):
- "title": etiqueta/gancho CORTO de 3-5 palabras (ej: "LA IA NO PARA", "ESTO CAMBIA TODO")
- "subtitle": titular PRINCIPAL (15-25 palabras) con **doble asterisco** SOLO en 1 o 2 FRASES CLAVE que deben ir en otro color. Lo resaltado debe ser la parte de shock/acción/emoción.

EJEMPLOS DE COVER:
- title: "LA IA NO PARA", subtitle: "AQUÍ TIENES LAS **NOTICIAS MÁS IMPORTANTES** DE LOS ÚLTIMOS 7 DÍAS"
- title: "ALERTA TECH", subtitle: "OPENAI ACABA DE **LANZAR GPT-5** Y LO CAMBIA TODO EN LA IA"
- title: "NO VAS A CREERLO", subtitle: "GOOGLE **ELIMINARÁ 10.000 EMPLEOS** POR CULPA DE LA IA"
- title: "OJO CON ESTO", subtitle: "META **DEJÓ QUE UNA IA BORRARA** TODA LA BASE DE DATOS POR ERROR"

FÓRMULAS DE HOOK VIRAL para el subtítulo:
1. SHOCK: abre con un dato impactante "**80% DE PROGRAMADORES** SERÁN REEMPLAZADOS EN 2026"
2. PREGUNTA: "¿SABÍAS QUE LA IA YA PUEDE **REEMPLAZAR A TU MÉDICO**?"
3. PROMESA: "5 HERRAMIENTAS IA QUE **TE AHORRAN 10 HORAS** POR SEMANA"
4. MITO/ERROR: "ESTÁS USANDO CHATGPT **COMPLETAMENTE MAL** Y NO LO SABES"
5. CURIOSIDAD: "GOOGLE ACABA DE HACER ALGO **INCREÍBLE** CON LA IA"

ESTRUCTURA NARRATIVA (MUY IMPORTANTE):
- Planifica los {num_content_slides} slides de contenido como una HISTORIA COHERENTE con flujo lógico, no como hechos aislados
- Arco sugerido: Slide 1 = Qué pasó/noticia → Slides 2-3 = Detalles y datos clave → Slides 4-5 = Por qué importa/impacto → Slide 6 = Qué viene ahora/conclusión
- Cada slide DEBE ser AUTOCONTENIDO: debe entregar una idea completa. NUNCA dejes preguntas abiertas ni "lo veremos luego"
- Si un slide menciona un problema, debe incluir también respuesta o contexto en ese mismo slide
- Cada slide debe aportar VALOR CONCRETO: dato, número, insight práctico o conclusión clara
- Prioriza DATOS ESPECÍFICOS sobre hype: nombres, cifras, fechas, porcentajes, comparaciones, precios
- Evita repetir ideas: cada slide debe aportar información NUEVA

REGLAS:
- Todo el texto en ESPAÑOL y MAYÚSCULAS para title/subtitle del cover
- Cada slide de contenido: máximo 32 palabras
- Resaltados con ** (MUY IMPORTANTE):
  - Cover subtitle: máximo 2 fragmentos resaltados
  - Slides de contenido/CTA: máximo 1 fragmento resaltado por campo (title o body)
  - Nunca resaltes frases largas: 2-4 palabras por resaltado
- Maquetación del body (MUY IMPORTANTE):
  - Escribe en bloques cortos: 2-4 líneas breves separadas con saltos de línea `\n` cuando ayude a la lectura
  - Evita párrafos largos tipo "muro de texto"
  - Si el slide es de pasos o instrucciones, usa lista numerada: `1. ...\n2. ...\n3. ...`
- Claridad y valor (OBLIGATORIO):
  - No inventes etiquetas ambiguas o grandilocuentes sin explicar (ej: "agentes del caos")
  - Cada slide debe dejar una idea cerrada: qué es + por qué importa + dato concreto
  - Si aparece un término técnico, explícalo en lenguaje simple dentro del mismo slide
  - No inventes datos fuera de KEY POINTS/CONTEXT; si falta una cifra, no la fabriques
  - Cada slide de contenido debe corresponder al key point del mismo orden (slide 1 ↔ key point 1, etc.)
  - Cada body debe incluir al menos un dato verificable del key point (número, empresa, producto, organismo o fecha)
  - Evita frases vacías tipo "increíble/revolucionario" si no van acompañadas de evidencia
- Usa datos concretos: números, nombres, fechas
- Tono: directo, potente, ligeramente provocador — NO aburrido ni genérico
- Slides de contenido: una idea clara por slide, fácil de entender
- Slide CTA: crear urgencia — "Guarda AHORA antes de que...", "Sígueme para no perderte..."
- Usa emojis relevantes con moderación (1-2 por slide)

REGLAS DEL CAPTION:
- Empieza con pregunta HOOK o afirmación fuerte (nunca con descripción plana)
- 300-500 caracteres con estructura hook → contexto → pregunta CTA
- Termina con una pregunta que invite comentarios

También genera:
- Alt text para accesibilidad (describe el contenido en 1-2 frases)
- 5 hashtags contextuales específicos de este tema

Responde en este formato JSON exacto:
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
    """Replace vague labels with clearer wording for standalone comprehension."""
    clean = str(text or "")
    clean = re.sub(
        r"\bagentes del caos\b",
        "agentes autónomos con comportamiento impredecible",
        clean,
        flags=re.IGNORECASE,
    )
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


def _compact_fact(text: str, max_words: int = 20) -> str:
    words = str(text or "").split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words]) + "..."


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
    return f"{body_clean}\nDato clave: {fact}"


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
        title = _safe_text(src.get("title")) or f"PUNTO CLAVE {i + 1}"
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

    # Try Prompt Director for an optimized prompt
    director_prompt = None
    try:
        from modules.prompt_director import PromptDirector
        director = PromptDirector()
        director_prompt = director.craft_content_prompt(topic)
    except Exception as e:
        logger.warning(f"Could not use Prompt Director for content: {e}")

    if director_prompt:
        prompt = director_prompt
        logger.info("Using director-crafted content prompt")
    else:
        logger.info("Using default content prompt")
        try:
            template = load_prompt("content_fallback", _DEFAULT_CONTENT_FALLBACK)
            prompt = template.format(
                topic=topic_text,
                key_points=key_points_text,
                context=context_text,
                total_slides=total_slides,
                num_content_slides=num_content_slides,
            )
        except (KeyError, IndexError) as e:
            logger.warning(f"Custom content_fallback prompt error: {e}. Using default.")
            prompt = _DEFAULT_CONTENT_FALLBACK.format(
                topic=topic_text,
                key_points=key_points_text,
                context=context_text,
                total_slides=total_slides,
                num_content_slides=num_content_slides,
            )

    def _call_openai(p):
        # OpenAI requires the word "json" in messages when using json_object format
        if "json" not in p.lower():
            p += "\n\nRespond in valid JSON format."
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": p}],
            temperature=0.8,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)

    content = _call_openai(prompt)

    # Validate structure/text — if director prompt produced bad output, retry with hardcoded
    if "slides" not in content or len(content.get("slides", [])) < 3 or _has_missing_slide_text(content):
        if director_prompt:
            logger.warning("Director prompt produced invalid or incomplete content. Retrying with default prompt.")
            fallback_prompt = _DEFAULT_CONTENT_FALLBACK.format(
                topic=topic_text,
                key_points=key_points_text,
                context=context_text,
                total_slides=total_slides,
                num_content_slides=num_content_slides,
            )
            content = _call_openai(fallback_prompt)
            if "slides" not in content or len(content.get("slides", [])) < 3:
                raise ValueError(f"Invalid content structure: {list(content.keys())}")
        else:
            raise ValueError(f"Invalid content structure: expected slides, got {list(content.keys())}")

    repaired = _normalize_content(content, topic)
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
        "topic": "OpenAI lanza GPT-5 con razonamiento avanzado",
        "topic_en": "OpenAI launches GPT-5 with advanced reasoning",
        "why": "Major AI model release with significant improvements",
        "key_points": [
            "GPT-5 supera a GPT-4 en un 40% en benchmarks de razonamiento",
            "Nuevo modo de 'pensamiento profundo' para problemas complejos",
            "Disponible en ChatGPT Plus y API desde el primer día",
            "Capacidad multimodal mejorada: texto, imagen, audio y video",
            "Precio de API reducido un 50% respecto a GPT-4",
            "OpenAI afirma que es un paso hacia AGI",
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
