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

from config.settings import DIRECTOR_MODEL, IMAGE_PROVIDER, OPENAI_API_KEY
from modules.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


def _is_viable_content_prompt(prompt_text: str) -> bool:
    """
    Lightweight guardrail to avoid returning weak content prompts.
    """
    text = str(prompt_text or "").strip()
    if len(text) < 300:
        return False
    low = text.lower()
    required = ("json", "slides", "caption", "alt_text", "hashtag_suggestions")
    if any(token not in low for token in required):
        return False
    if "8 slides" not in low and "exactamente 8" not in low:
        return False
    return True


# ── Default meta-prompts (editable via dashboard) ────────────────────────────

_DEFAULT_RESEARCH_META = """Eres un/a Prompt Engineer. Tu trabajo es escribir el MEJOR prompt posible
para un modelo GPT-4o-mini que seleccione un tema de actualidad para "TechTokio ⚡ 30s".

CONTEXTO de la ejecución de hoy:
- Día de la semana: {day_name}
- Número de artículos candidatos: {num_articles}
- Hay datos de Google Trends: {has_trends}
- Número de temas pasados a evitar: {past_count}

El prompt que escribas debe:
1. Ser para una cuenta de Instagram en español con aura Neo-Tokio.
2. Incluir placeholders para: {{articles}}, {{trends}}, {{past_topics}}
3. Pedir salida JSON con: topic, topic_en, why, key_points (6), source_urls, virality_score
4. Priorizar: recencia, corroboración entre medios, relevancia tech/IA y utilidad práctica.
5. Exigir fidelidad a fuentes: no inventar datos y no ampliar el alcance de la noticia.
6. Pedir key_points autocontenidos, claros y "sin humo".
7. Mantener estilo editorial de marca: directo, afilado, humor inteligente.
8. Ser claro y de menos de 500 palabras.

Escribe SOLO el texto del prompt. Sin explicación y sin envolver en markdown."""

_DEFAULT_CONTENT_META = """Eres un/a Prompt Engineer especializado/a en contenido VIRAL de Instagram.
Tu trabajo es escribir un prompt excelente para un modelo GPT-4o-mini que genere
un carrusel claro, fiel a la noticia y con el branding "TechTokio ⚡ 30s".

TEMA A CUBRIR:
- Título (ES): {topic_title}
- Título (EN): {topic_en}
- Puntos clave: {key_points}
- Puntuación de viralidad: {virality}/10

CONTEXTO:
- Día: {day_name}
- Guía de tono: {tone_hint}
- Estilo de contenido: {style_hint}

Tu prompt generado debe incluir reglas simples y estrictas:
1. Salida JSON con: slides, caption, alt_text, hashtag_suggestions.
2. Exactamente 8 slides: 1 cover + 6 contenido + 1 CTA.
3. Cover:
   - title: 3-5 palabras, gancho fuerte.
   - subtitle: 12-24 palabras, preciso + clickbait sin exagerar.
4. Slides de contenido:
   - Uno por cada key point en orden.
   - Entre 38 y 65 palabras por slide.
   - Idea cerrada, útil y fácil de entender.
   - Cada body debe explicar un hecho concreto, su contexto y su consecuencia práctica.
   - Evitar plantillas repetitivas (ej. "Por qué importa:", "Dato clave:").
   - Cuando ayude a la lectura, usar 2 bloques cortos separados por salto de línea.
5. Fidelidad:
   - No inventar datos fuera de key_points/contexto.
   - Mantener el alcance exacto de la noticia.
6. Estilo de marca:
   - Español claro, directo, afilado, con humor inteligente.
   - Cero humo: no frases vacías ni grandilocuentes.
   - Títulos de contenido concretos y naturales; no uses etiquetas/códigos prefijo tipo RADAR, TOOL, 速報, 判定.
   - Resaltados con `**` limitados (máx. 2 en cover subtitle; máx. 1 por campo en contenido/CTA).
7. Caption:
   - 250-500 caracteres.
   - Hook inicial + resumen + pregunta final.
8. Incluir el sello "TechTokio ⚡ 30s" una vez (en CTA o caption).
9. Incluir alt_text y 5 hashtags relevantes.

TONO: {tone_hint}
ESTILO: {style_hint}

Escribe SOLO el texto del prompt con los datos del tema embebidos.
Sin explicación y sin envolver en markdown."""

_DEFAULT_IMAGE_META = """Eres un/a Prompt Engineer para generación de imágenes con IA,
especializado/a en portadas virales para la marca "TechTokio ⚡ 30s".

La imagen se usará en el 50% superior del cover del carrusel. El texto va en la mitad inferior.

TOPIC: {topic_en}

TU TAREA:
Crea un prompt que genere una imagen DIRECTAMENTE RELACIONADA con este tema.
Evita oficinas genéricas y metáforas abstractas sin conexión.
La imagen debe ser reconocible al instante como parte de la identidad Neo-Tokio.

ESTILO:
- Ilustración SIMPLE y legible, estética nocturna + neón.
- Paleta de marca: carbón oscuro, blanco y acento azul eléctrico.
- Look editorial moderno, personal y expresivo.
- No fotorrealismo, no render 3D, no look stock.

REGLAS DE COMPOSICIÓN (NO NEGOCIABLES):
- Define un ÚNICO SUJETO HÉROE que represente claramente el tema (producto/objeto/dispositivo/contexto).
- Máximo 2 elementos secundarios. Evita escenas recargadas o fondos muy complejos.
- El SUJETO HÉROE debe estar en la MITAD SUPERIOR (top 45-55%), grande y claramente visible.
- Mantén el 45% inferior limpio/oscuro como espacio negativo (ahí irá el texto).
- NO permitas que elementos de fondo irrelevantes dominen más que el sujeto héroe.
- Si el tema es un producto físico (ej: relojes de lujo), muéstralo claramente en la mitad superior, en foco.

REGLAS DE SEGURIDAD (OBLIGATORIAS):
- NUNCA nombres personas reales (no "Elon Musk", "Tim Cook", etc.)
- NUNCA referencias logos de marca ni diseños registrados
- Usa descripciones genéricas: "un gamer", "una ejecutiva tech", "un smartphone"

REGLA ABSOLUTA — SIN TEXTO EN LA IMAGEN:
- La imagen generada NO debe contener NINGÚN texto, letra, número, palabra, marca de agua, etiqueta ni firma.
- Termina tu prompt con: "Sin texto, sin letras, sin palabras, sin números en ninguna parte de la imagen."

Escribe un prompt corto (2-3 frases, máximo 100 palabras).
Escribe SOLO el prompt de generación de imagen. Sin explicación."""

_XAI_IMAGE_META = """You are a Prompt Engineer for AI image generation, specializing in
viral Instagram cover images for a tech news account.

The image will be used as the TOP 50% of a carousel cover slide. Text goes on the bottom half.

TOPIC: {topic_en}

YOUR TASK:
Create a prompt that generates an image DIRECTLY RELATED to this specific topic.
Make the image IMMEDIATELY recognizable as related to "{topic_en}".

CELEBRITY / PERSON RULES:
- If the topic is about a specific well-known person (CEO, founder, politician, celebrity, streamer),
  INCLUDE THEM BY FULL NAME in the prompt (e.g. "Elon Musk", "Sam Altman", "Tim Cook").
  For streamers or internet personalities, also add a brief physical description
  (e.g. "ElXokas, a bearded Spanish man with glasses") to help the model generate their likeness.
  Show them in a dramatic, cinematic portrait style — face clearly visible, looking at camera.
- If no specific person is involved, use compelling visual metaphors instead.

BRAND / LOGO RULES:
- If the topic is about a specific company or product, INCLUDE the brand name or logo
  in the prompt (e.g. "Apple logo", "Tesla Model Y", "OpenAI logo").
- Show the product or branding prominently.

VISUAL METAPHOR examples (when no person/brand applies):
- Topic about gaming → gaming setup, controller, gaming room with screens
- Topic about AI → futuristic robot, neural network visualization
- Topic about a hack/security → hooded figure, glitch effects, broken screen
- Topic about space/science → astronaut, planet, lab with equipment

STYLE:
- Dramatic cinematic lighting, dark moody tones with neon/teal accents
- Photorealistic quality, shallow depth of field
- Subject in upper half of frame, bottom can be dark/empty (text goes there)
- Portrait orientation (3:4 aspect ratio), optimized for Instagram carousel

ABSOLUTE RULE — NO TEXT IN THE IMAGE:
- The generated image must contain ZERO text, letters, numbers, words, watermarks, labels, or captions.
- Do NOT include any text in your prompt. If you mention a logo, describe it visually (shape, colors) but NEVER ask for text on it.
- End your prompt with: "No text, no letters, no words, no numbers anywhere in the image."

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
                tone_hint = "alto impacto y urgencia, sin exagerar ni inventar"
            elif virality >= 7:
                tone_hint = "informativo, seguro y basado en datos verificables"
            else:
                tone_hint = "didáctico, curioso y útil, con enfoque práctico"

            # Determine content style by topic type
            topic_lower = topic_en.lower()
            if any(w in topic_lower for w in ["launch", "release", "announce", "new"]):
                style_hint = "Incluir comparativa con la versión anterior, mejoras reales y precio/disponibilidad"
            elif any(w in topic_lower for w in ["security", "hack", "breach", "vulnerability"]):
                style_hint = "Explicar a quién afecta, nivel de riesgo y acciones concretas para protegerse"
            elif any(w in topic_lower for w in ["product", "tool", "app", "service"]):
                style_hint = "Comparar alternativas, destacar diferenciales reales y casos de uso"
            else:
                style_hint = "Aterrizar por qué importa hoy, impacto real y qué viene después"

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
                temperature=0.4,
                max_tokens=1500,
            )

            crafted = response.choices[0].message.content.strip()
            if not _is_viable_content_prompt(crafted):
                logger.warning("Director content prompt failed viability checks")
                return None
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

            # Pick meta-prompt based on provider: xAI allows celebrities & logos
            if IMAGE_PROVIDER == "xai":
                default_meta = _XAI_IMAGE_META
                prompt_id = "image_meta_xai"
            else:
                default_meta = _DEFAULT_IMAGE_META
                prompt_id = "image_meta"

            try:
                tmpl = load_prompt(prompt_id, default_meta)
                meta_prompt = tmpl.format(topic_en=topic_en)
            except (KeyError, IndexError) as e:
                logger.warning(f"Custom {prompt_id} prompt error: {e}. Using default.")
                meta_prompt = default_meta.format(topic_en=topic_en)

            response = self.client.chat.completions.create(
                model=DIRECTOR_MODEL,
                messages=[{"role": "user", "content": meta_prompt}],
                temperature=0.9,
                max_tokens=300,
            )

            crafted = response.choices[0].message.content.strip()
            # Hard guardrail to keep subject placement stable for cover composition.
            crafted += (
                " Composición obligatoria: un único sujeto héroe directamente relacionado con "
                f"'{topic_en}', dominante y en foco en la mitad superior (45-55%); "
                "el 45% inferior debe quedar oscuro, limpio y libre para texto; "
                "ningún elemento secundario puede dominar la escena. "
                "Estilo obligatorio: ilustración editorial dibujada a mano, con textura personal de tinta/pincel; "
                "prohibido fotorealismo."
            )
            if cover_text:
                crafted += (
                    f" Pista del titular: '{cover_text}'. "
                    "El sujeto héroe debe corresponder al sustantivo/contexto concreto del titular."
                )
            logger.info(f"Director crafted image prompt: {crafted[:80]}...")
            return crafted

        except Exception as e:
            logger.warning(f"Prompt Director failed for cover image: {e}")
            return None
