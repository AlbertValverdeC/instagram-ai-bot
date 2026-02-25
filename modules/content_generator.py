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

logger = logging.getLogger(__name__)


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

    prompt = f"""You are a top-tier Instagram content creator for a Spanish-language Tech/AI account.
Create a carousel post about the following topic.

TOPIC: {topic['topic']}
KEY POINTS: {json.dumps(topic['key_points'], ensure_ascii=False)}
CONTEXT: {topic.get('why', '')}

Generate a carousel with exactly {NUM_CONTENT_SLIDES + 2} slides (1 cover + {NUM_CONTENT_SLIDES} content + 1 CTA).

RULES:
- All text in SPANISH
- Each slide: max 40 words
- Use concrete data: numbers, names, dates
- Tone: informative, accessible, not overly technical
- Cover slide: catchy hook that makes people stop scrolling
- Content slides: one clear idea per slide, easy to understand
- CTA slide: encourage saves, shares, and follows
- Include relevant emojis sparingly (1-2 per slide)

Also generate:
- An Instagram caption (300-500 chars) with hook → context → CTA question
- Alt text for accessibility (describe the carousel content in 1-2 sentences)
- 5 contextual hashtag suggestions specific to this topic

Respond in this exact JSON format:
{{
    "slides": [
        {{
            "type": "cover",
            "title": "Main hook title (short, impactful)",
            "subtitle": "Brief context line"
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
            "title": "CTA headline",
            "body": "CTA message encouraging engagement"
        }}
    ],
    "caption": "Instagram caption text here",
    "alt_text": "Accessibility description of the carousel",
    "hashtag_suggestions": ["#hashtag1", "#hashtag2", "#hashtag3", "#hashtag4", "#hashtag5"]
}}"""

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        response_format={"type": "json_object"},
    )

    content = json.loads(response.choices[0].message.content)

    # Validate structure
    if "slides" not in content or len(content["slides"]) < 3:
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
