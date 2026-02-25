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

from openai import OpenAI

from config.settings import (
    NUM_CONTENT_SLIDES,
    OPENAI_API_KEY,
    OPENAI_MODEL,
)
from modules.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


# ── Default fallback prompt (editable via dashboard) ─────────────────────────

_DEFAULT_CONTENT_FALLBACK = """You are a VIRAL Instagram content creator for a Spanish-language Tech/AI account.
Create an IRRESISTIBLE carousel post about the following topic.

TOPIC: {topic}
KEY POINTS: {key_points}
CONTEXT: {context}

Generate a carousel with exactly {total_slides} slides (1 cover + {num_content_slides} content + 1 CTA).

COVER SLIDE FORMAT (very important):
- "title": a SHORT tag/hook in 3-5 words (e.g., "LA IA NO PARA", "ESTO CAMBIA TODO")
- "subtitle": the MAIN headline (15-25 words) with **double asterisks** around the KEY PHRASES that should be highlighted in a different color. The highlighted part is the shocking/action/emotional part.

COVER EXAMPLES:
- title: "LA IA NO PARA", subtitle: "AQUÍ TIENES LAS **NOTICIAS MÁS IMPORTANTES** DE LOS ÚLTIMOS 7 DÍAS"
- title: "ALERTA TECH", subtitle: "OPENAI ACABA DE **LANZAR GPT-5** Y LO CAMBIA TODO EN LA IA"
- title: "NO VAS A CREERLO", subtitle: "GOOGLE **ELIMINARÁ 10.000 EMPLEOS** POR CULPA DE LA IA"
- title: "OJO CON ESTO", subtitle: "META **DEJÓ QUE UNA IA BORRARA** TODA LA BASE DE DATOS POR ERROR"

VIRAL HOOK FORMULAS for the subtitle:
1. SHOCK: Lead with a jaw-dropping fact "**80% DE PROGRAMADORES** SERÁN REEMPLAZADOS EN 2026"
2. QUESTION: "¿SABÍAS QUE LA IA YA PUEDE **REEMPLAZAR A TU MÉDICO**?"
3. PROMISE: "5 HERRAMIENTAS IA QUE **TE AHORRAN 10 HORAS** POR SEMANA"
4. MYTH: "ESTÁS USANDO CHATGPT **COMPLETAMENTE MAL** Y NO LO SABES"
5. CURIOSITY: "GOOGLE ACABA DE HACER ALGO **INCREÍBLE** CON LA IA"

NARRATIVE STRUCTURE (VERY IMPORTANT):
- Plan the {num_content_slides} content slides as a COHERENT STORY with a logical flow, not isolated facts
- Suggested arc: Slide 1 = What happened / the news → Slides 2-3 = Key details and data → Slides 4-5 = Why it matters / impact → Slide 6 = What comes next / conclusion
- Each slide MUST be SELF-CONTAINED: it should deliver a complete idea. NEVER leave open questions, cliffhangers, or "we'll explain later" between content slides
- If a slide mentions a problem, it must also give the answer or context — don't split a question and its answer across two slides
- Every slide should give the reader something VALUABLE: a fact, a number, a practical insight, or a clear takeaway. Avoid vague statements like "this could change everything" without saying HOW
- Prioritize SPECIFIC DATA over hype: names, numbers, dates, percentages, comparisons, prices
- Avoid repeating the same idea across slides — each slide must add NEW information

RULES:
- ALL text in SPANISH and UPPERCASE for cover title and subtitle
- Each content slide: max 40 words
- Use concrete data: numbers, names, dates
- Tone: bold, direct, slightly provocative — NOT boring or generic
- Content slides: one clear idea per slide, easy to understand
- CTA slide: create urgency — "Guarda AHORA antes de que...", "Sígueme para no perderte..."
- Include relevant emojis sparingly (1-2 per slide)

CAPTION RULES:
- Start with a HOOK question or bold statement (never start with a description)
- 300-500 chars with hook → context → CTA question
- End with a question that invites comments

Also generate:
- Alt text for accessibility (describe the carousel content in 1-2 sentences)
- 5 contextual hashtag suggestions specific to this topic

Respond in this exact JSON format:
{{
    "slides": [
        {{
            "type": "cover",
            "title": "SHORT TAG HOOK (3-5 words)",
            "subtitle": "MAIN HEADLINE WITH **HIGHLIGHTED KEY PHRASES** IN DOUBLE ASTERISKS"
        }},
        {{
            "type": "content",
            "number": 1,
            "title": "Short slide title",
            "body": "Explanation text with data"
        }},
        {{
            "type": "content",
            "number": 2,
            "title": "Short slide title",
            "body": "Explanation text with data"
        }},
        {{
            "type": "content",
            "number": 3,
            "title": "Short slide title",
            "body": "Explanation text with data"
        }},
        {{
            "type": "content",
            "number": 4,
            "title": "Short slide title",
            "body": "Explanation text with data"
        }},
        {{
            "type": "content",
            "number": 5,
            "title": "Short slide title",
            "body": "Explanation text with data"
        }},
        {{
            "type": "content",
            "number": 6,
            "title": "Short slide title",
            "body": "Explanation text with data"
        }},
        {{
            "type": "cta",
            "title": "CTA headline with urgency",
            "body": "CTA message encouraging saves, shares, follows"
        }}
    ],
    "caption": "Instagram caption starting with a HOOK",
    "alt_text": "Accessibility description of the carousel",
    "hashtag_suggestions": ["#hashtag1", "#hashtag2", "#hashtag3", "#hashtag4", "#hashtag5"]
}}"""


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

    # Validate structure — if director prompt produced bad output, retry with hardcoded
    if "slides" not in content or len(content.get("slides", [])) < 3:
        if director_prompt:
            logger.warning(f"Director prompt produced invalid content: {list(content.keys())}. Retrying with default prompt.")
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

    logger.info(f"Generated {len(content['slides'])} slides + caption")
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
