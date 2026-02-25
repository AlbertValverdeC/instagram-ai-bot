"""
Prompt Director: uses GPT-4o to craft optimized prompts for downstream models.

Generates dynamic, context-aware prompts for:
  - Research ranking (researcher.py)
  - Content generation (content_generator.py)
  - Cover image generation (image_generator.py)

Each method returns None on failure so callers can fall back to hardcoded prompts.
"""

import logging
from datetime import datetime

from openai import OpenAI

from config.settings import DIRECTOR_MODEL, OPENAI_API_KEY
from modules.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


# ── Default meta-prompts (editable via dashboard) ────────────────────────────

_DEFAULT_RESEARCH_META = """You are a Prompt Engineer. Your job is to write the BEST possible prompt
for a GPT-4o-mini model that will rank and select trending tech/AI topics for a Spanish-language
Instagram carousel post.

CONTEXT about today's run:
- Day of the week: {day_name}
- Number of candidate articles: {num_articles}
- Google Trends data available: {has_trends}
- Number of past topics to avoid: {past_count}

ADAPTATIONS to apply:
- If Monday: bias towards forward-looking topics (launches, predictions, roadmaps)
- If Friday: bias towards weekly recap or "best of the week" angles
- If past_count > 15: strongly emphasize diversity and novelty in topic selection
- If few articles (<10): tell the model to be more creative combining related stories
- If many articles (>30): tell the model to prioritize recency and virality

The prompt you write must:
1. Be for a Spanish-language Instagram account about Tech/AI
2. Include placeholders for: {{articles}}, {{trends}}, {{past_topics}}
3. Request JSON output with: topic, topic_en, why, key_points (6), source_urls, virality_score
4. Include scoring criteria (virality, breadth, substance, freshness)
5. Be clear, specific, and under 800 words

Write ONLY the prompt text. No explanation, no markdown wrapping."""

_DEFAULT_CONTENT_META = """You are a Prompt Engineer specializing in VIRAL Instagram content.
Your job is to write the BEST possible prompt for a GPT-4o-mini model that will generate
Instagram carousel content in Spanish with MAXIMUM scroll-stopping power.

TOPIC TO COVER:
- Title (ES): {topic_title}
- Title (EN): {topic_en}
- Key points: {key_points}
- Virality score: {virality}/10

CONTEXT:
- Day: {day_name}
- Tone guidance: {tone_hint}
- Content style: {style_hint}

VIRAL HOOK FORMULAS — The cover slide title MUST use one of these patterns:
1. QUESTION HOOK: Provoke curiosity with a question the reader can't ignore
   Examples: "¿Tu trabajo desaparece en 2026?", "¿Sabías que la IA ya puede...?"
2. SHOCK / STATISTIC: Lead with a jaw-dropping number or fact
   Examples: "El 80% de los programadores serán reemplazados", "1 millón de empleos perdidos en 90 días"
3. PROMISE / BENEFIT: Promise a transformation or exclusive knowledge
   Examples: "5 herramientas IA que te ahorran 10 horas/semana", "Así ganan $10K/mes con IA"
4. MISTAKE / MYTH: Challenge a common belief to create cognitive dissonance
   Examples: "Estás usando ChatGPT MAL", "Lo que nadie te dice sobre la IA"
5. CURIOSITY / CLIFFHANGER: Create an information gap that demands resolution
   Examples: "Google acaba de hacer algo INCREÍBLE", "La IA que asusta hasta a Elon Musk"
6. STEP-BY-STEP / LIST: Promise structured, digestible value
   Examples: "7 IAs que cambiarán tu vida en 2026", "3 pasos para dominar la IA"

COVER SLIDE FORMAT (VERY IMPORTANT):
- "title": SHORT tag/hook in 3-5 words ALL CAPS (e.g., "LA IA NO PARA", "ALERTA TECH")
- "subtitle": MAIN headline in ALL CAPS (15-25 words) with **double asterisks** around the
  KEY PHRASES that should be highlighted in a different color.
  Example: "AQUÍ TIENES LAS **NOTICIAS MÁS IMPORTANTES** DE LOS ÚLTIMOS 7 DÍAS"
  Example: "OPENAI ACABA DE **LANZAR GPT-5** Y LO CAMBIA TODO EN LA IA"

NARRATIVE COHERENCE (VERY IMPORTANT — include these rules in your prompt):
- The 6 content slides must follow a LOGICAL NARRATIVE ARC, not be random isolated facts
- Suggested flow: What happened → Key details/data → Why it matters → What comes next
- Each slide must be SELF-CONTAINED: deliver a complete idea, NEVER leave open questions or cliffhangers between slides
- If a slide poses a question or problem, it MUST also provide the answer in the SAME slide
- Every slide must provide CONCRETE VALUE: specific facts, numbers, dates, comparisons — avoid vague hype like "this changes everything" without explaining HOW
- No repetition: each slide adds NEW information

CRITICAL RULES for the prompt you write:
1. The cover subtitle MUST be clickbait/viral using one of the 6 hook formulas above
2. The cover title is a SHORT tag (3-5 words), the subtitle is the MAIN headline with **highlights**
3. Generate exactly 8 slides: 1 cover + 6 content + 1 CTA
4. All text in SPANISH
5. Max 40 words per slide
6. Content slides: one idea per slide with concrete data (numbers, names, dates)
7. CTA slide: encourage saves, shares, follows with urgency
8. Also generate: caption (300-500 chars), alt_text, 5 hashtag suggestions
9. Caption must start with a hook question or bold statement, NOT a description
10. Request JSON output matching this exact structure:
    slides[] (type, title, subtitle/body/number), caption, alt_text, hashtag_suggestions

TONE: {tone_hint}
STYLE: {style_hint}

Write ONLY the prompt text with the topic data embedded. No explanation, no markdown wrapping."""

_DEFAULT_IMAGE_META = """You are a Prompt Engineer for AI image generation, specializing in
viral Instagram cover images for a tech news account.

The image will be used as the TOP 50% of a carousel cover slide. Text goes on the bottom half.

TOPIC: {topic_en}

YOUR TASK:
Create a prompt that generates an image DIRECTLY RELATED to this specific topic.
Do NOT default to "generic office meeting" — think about what VISUAL METAPHOR best represents
the topic. Examples:
- Topic about gaming/consoles → gaming setup, controller, gaming room with screens
- Topic about AI → futuristic robot, neural network visualization, AI brain concept
- Topic about a hack/security → hooded figure, glitch effects, broken screen
- Topic about a company → product being used, dramatic product shot, workspace with the product
- Topic about social media → smartphone screens, content feeds, person scrolling
- Topic about space/science → astronaut, planet, lab with equipment

The image must be IMMEDIATELY recognizable as related to "{topic_en}".

STYLE:
- Dramatic cinematic lighting, dark moody tones with neon/teal accents
- Photorealistic quality, shallow depth of field
- Subject in upper half of frame, bottom can be dark/empty (text goes there)

SAFETY RULES (MUST follow or image will be blocked):
- NEVER name real people (no "Elon Musk", "Tim Cook", etc.)
- NEVER reference brand logos or trademarked designs
- Use generic descriptions: "a gamer", "a tech executive", "a smartphone"
- NO text, letters, numbers, or words in the image

Write a short prompt (2-3 sentences, max 100 words).
Write ONLY the image generation prompt. No explanation."""


class PromptDirector:
    """Crafts optimized prompts for downstream AI models."""

    def __init__(self):
        self._client = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(api_key=OPENAI_API_KEY)
        return self._client

    def craft_research_prompt(
        self,
        articles_text: str,
        trends_text: str,
        past_text: str,
    ) -> str | None:
        """
        Craft an optimized prompt for topic ranking.

        Returns the prompt string, or None if the director fails.
        """
        try:
            now = datetime.now()
            day_name = now.strftime("%A")
            num_articles = articles_text.count("\n") + 1
            has_trends = "No Google Trends" not in trends_text
            past_count = len([t for t in past_text.split(", ") if t and t != "None"])

            try:
                template = load_prompt("research_meta", _DEFAULT_RESEARCH_META)
                meta_prompt = template.format(
                    day_name=day_name,
                    num_articles=num_articles,
                    has_trends=has_trends,
                    past_count=past_count,
                )
            except (KeyError, IndexError) as e:
                logger.warning(f"Custom research_meta prompt error: {e}. Using default.")
                meta_prompt = _DEFAULT_RESEARCH_META.format(
                    day_name=day_name,
                    num_articles=num_articles,
                    has_trends=has_trends,
                    past_count=past_count,
                )

            response = self.client.chat.completions.create(
                model=DIRECTOR_MODEL,
                messages=[{"role": "user", "content": meta_prompt}],
                temperature=0.6,
                max_tokens=1500,
            )

            crafted = response.choices[0].message.content.strip()

            # Replace placeholders with actual data
            crafted = crafted.replace("{articles}", articles_text)
            crafted = crafted.replace("{trends}", trends_text)
            crafted = crafted.replace("{past_topics}", past_text)

            logger.info(f"Director crafted research prompt ({len(crafted)} chars)")
            return crafted

        except Exception as e:
            logger.warning(f"Prompt Director failed for research: {e}")
            return None

    def craft_content_prompt(self, topic: dict) -> str | None:
        """
        Craft an optimized prompt for carousel content generation.

        Returns the prompt string, or None if the director fails.
        """
        try:
            import json as _json

            now = datetime.now()
            day_name = now.strftime("%A")
            virality = topic.get("virality_score", 7)
            topic_title = topic.get("topic", "")
            topic_en = topic.get("topic_en", "")
            key_points = _json.dumps(topic.get("key_points", []), ensure_ascii=False)

            # Determine tone and style guidance
            if virality >= 9:
                tone_hint = "dramatic, high-impact, urgency — this is breaking news"
            elif virality >= 7:
                tone_hint = "informative, confident, data-driven — solid trending story"
            else:
                tone_hint = "exploratory, curious, educational — niche but interesting"

            # Determine content style by topic type
            topic_lower = topic_en.lower()
            if any(w in topic_lower for w in ["launch", "release", "announce", "new"]):
                style_hint = "Include benchmarks, comparisons with previous versions, and pricing"
            elif any(w in topic_lower for w in ["security", "hack", "breach", "vulnerability"]):
                style_hint = "Create urgency, explain who is affected, and provide actionable advice"
            elif any(w in topic_lower for w in ["product", "tool", "app", "service"]):
                style_hint = "Compare with alternatives, highlight unique features, include use cases"
            else:
                style_hint = "Focus on why this matters, real-world implications, and what comes next"

            try:
                template = load_prompt("content_meta", _DEFAULT_CONTENT_META)
                meta_prompt = template.format(
                    topic_title=topic_title,
                    topic_en=topic_en,
                    key_points=key_points,
                    virality=virality,
                    day_name=day_name,
                    tone_hint=tone_hint,
                    style_hint=style_hint,
                )
            except (KeyError, IndexError) as e:
                logger.warning(f"Custom content_meta prompt error: {e}. Using default.")
                meta_prompt = _DEFAULT_CONTENT_META.format(
                    topic_title=topic_title,
                    topic_en=topic_en,
                    key_points=key_points,
                    virality=virality,
                    day_name=day_name,
                    tone_hint=tone_hint,
                    style_hint=style_hint,
                )

            response = self.client.chat.completions.create(
                model=DIRECTOR_MODEL,
                messages=[{"role": "user", "content": meta_prompt}],
                temperature=0.7,
                max_tokens=1500,
            )

            crafted = response.choices[0].message.content.strip()
            logger.info(f"Director crafted content prompt ({len(crafted)} chars)")
            return crafted

        except Exception as e:
            logger.warning(f"Prompt Director failed for content: {e}")
            return None

    def craft_cover_image_prompt(
        self,
        topic: dict,
        cover_text: str,
        template: dict,
    ) -> str | None:
        """
        Craft a short image generation prompt for the cover slide background.

        Returns a 1-3 sentence prompt for Gemini Imagen, or None on failure.
        """
        try:
            topic_en = topic.get("topic_en", topic.get("topic", "technology"))
            bg = template.get("background", {})
            accent = template.get("accent_color", (0, 200, 255))
            color_top = bg.get("color_top", (10, 15, 40))
            color_bottom = bg.get("color_bottom", (25, 55, 109))

            try:
                tmpl = load_prompt("image_meta", _DEFAULT_IMAGE_META)
                meta_prompt = tmpl.format(topic_en=topic_en)
            except (KeyError, IndexError) as e:
                logger.warning(f"Custom image_meta prompt error: {e}. Using default.")
                meta_prompt = _DEFAULT_IMAGE_META.format(topic_en=topic_en)

            response = self.client.chat.completions.create(
                model=DIRECTOR_MODEL,
                messages=[{"role": "user", "content": meta_prompt}],
                temperature=0.9,
                max_tokens=300,
            )

            crafted = response.choices[0].message.content.strip()
            logger.info(f"Director crafted image prompt: {crafted[:80]}...")
            return crafted

        except Exception as e:
            logger.warning(f"Prompt Director failed for cover image: {e}")
            return None
