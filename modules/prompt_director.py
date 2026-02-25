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

_DEFAULT_RESEARCH_META = """Eres un/a Prompt Engineer. Tu trabajo es escribir el MEJOR prompt posible
para un modelo GPT-4o-mini que rankee y seleccione temas en tendencia de tech/IA para un
carrusel de Instagram en español.

CONTEXTO de la ejecución de hoy:
- Día de la semana: {day_name}
- Número de artículos candidatos: {num_articles}
- Hay datos de Google Trends: {has_trends}
- Número de temas pasados a evitar: {past_count}

ADAPTACIONES que debes aplicar:
- Si es Monday/Lunes: sesga hacia temas orientados al futuro (lanzamientos, predicciones, roadmaps)
- Si es Friday/Viernes: sesga hacia recap semanal o ángulos de "lo mejor de la semana"
- Si past_count > 15: enfatiza con fuerza diversidad y novedad en la selección
- Si hay pocos artículos (<10): pide más creatividad combinando historias relacionadas
- Si hay muchos artículos (>30): prioriza recencia y viralidad

El prompt que escribas debe:
1. Ser para una cuenta de Instagram en español sobre Tech/IA
2. Incluir placeholders para: {{articles}}, {{trends}}, {{past_topics}}
3. Pedir salida JSON con: topic, topic_en, why, key_points (6), source_urls, virality_score
4. Incluir criterios de puntuación (viralidad, amplitud, sustancia, frescura)
5. Ser claro, específico y de menos de 800 palabras

Escribe SOLO el texto del prompt. Sin explicación y sin envolver en markdown."""

_DEFAULT_CONTENT_META = """Eres un/a Prompt Engineer especializado/a en contenido VIRAL de Instagram.
Tu trabajo es escribir el MEJOR prompt posible para un modelo GPT-4o-mini que genere
contenido de carrusel en español con MÁXIMO poder de retención.

TEMA A CUBRIR:
- Título (ES): {topic_title}
- Título (EN): {topic_en}
- Puntos clave: {key_points}
- Puntuación de viralidad: {virality}/10

CONTEXTO:
- Día: {day_name}
- Guía de tono: {tone_hint}
- Estilo de contenido: {style_hint}

FÓRMULAS DE HOOK VIRAL — El titular del cover DEBE usar uno de estos patrones:
1. HOOK DE PREGUNTA: provoca curiosidad con una pregunta imposible de ignorar
   Ejemplos: "¿Tu trabajo desaparece en 2026?", "¿Sabías que la IA ya puede...?"
2. SHOCK / ESTADÍSTICA: abre con un dato impactante
   Ejemplos: "El 80% de los programadores serán reemplazados", "1 millón de empleos perdidos en 90 días"
3. PROMESA / BENEFICIO: promete transformación o conocimiento exclusivo
   Ejemplos: "5 herramientas IA que te ahorran 10 horas/semana", "Así ganan $10K/mes con IA"
4. ERROR / MITO: desafía una creencia común
   Ejemplos: "Estás usando ChatGPT MAL", "Lo que nadie te dice sobre la IA"
5. CURIOSIDAD / CLIFFHANGER: abre una brecha de información
   Ejemplos: "Google acaba de hacer algo INCREÍBLE", "La IA que asusta hasta a Elon Musk"
6. PASO A PASO / LISTA: promete valor estructurado y fácil de consumir
   Ejemplos: "7 IAs que cambiarán tu vida en 2026", "3 pasos para dominar la IA"

FORMATO DEL COVER (MUY IMPORTANTE):
- "title": etiqueta/gancho CORTO de 3-5 palabras en MAYÚSCULAS (ej: "LA IA NO PARA", "ALERTA TECH")
- "subtitle": titular PRINCIPAL en MAYÚSCULAS (15-25 palabras) con **doble asterisco**
  alrededor de 1 o 2 FRASES CLAVE que deben resaltarse en otro color.
  Ejemplo: "AQUÍ TIENES LAS **NOTICIAS MÁS IMPORTANTES** DE LOS ÚLTIMOS 7 DÍAS"
  Ejemplo: "OPENAI ACABA DE **LANZAR GPT-5** Y LO CAMBIA TODO EN LA IA"

COHERENCIA NARRATIVA (MUY IMPORTANTE — incluye estas reglas en tu prompt):
- Los 6 slides de contenido deben seguir un ARCO NARRATIVO LÓGICO, no hechos aislados
- Flujo sugerido: Qué pasó → Detalles/datos clave → Por qué importa → Qué viene después
- Cada slide debe ser AUTOCONTENIDO: entregar una idea completa, NUNCA dejar preguntas abiertas
- Si un slide plantea un problema o pregunta, DEBE dar respuesta en ESE MISMO slide
- Cada slide debe aportar VALOR CONCRETO: datos, números, fechas, comparaciones
- Evita repetición: cada slide debe añadir información NUEVA

REGLAS CRÍTICAS para el prompt que escribas:
1. El subtítulo del cover DEBE ser clickbait/viral usando una de las 6 fórmulas anteriores
2. El título del cover es CORTO (3-5 palabras), el subtítulo es el titular principal con **resaltados**
3. Genera exactamente 8 slides: 1 cover + 6 contenido + 1 CTA
4. Todo el texto en ESPAÑOL
5. Máximo 32 palabras por slide de contenido
6. Slides de contenido: una idea por slide con datos concretos (números, nombres, fechas)
7. Slide CTA: incentivar guardados, compartidos y follows con urgencia
8. También genera: caption (300-500 chars), alt_text, 5 hashtags sugeridos
9. El caption debe empezar con pregunta hook o afirmación fuerte, NO con descripción
10. Pedir salida JSON con esta estructura exacta:
    slides[] (type, title, subtitle/body/number), caption, alt_text, hashtag_suggestions
11. MAQUETACIÓN DE BODY: escribe en bloques cortos para lectura rápida; permite saltos de línea `\\n`.
    Si es un slide de pasos/guía, usa lista numerada (`1.`, `2.`, `3.`) en líneas separadas.
12. RESALTADOS CON `**`: evita exceso. Máximo 2 fragmentos en cover subtitle y máximo 1 fragmento por campo en contenido/CTA.
    Cada resaltado debe tener 2-4 palabras (no frases largas).
13. CLARIDAD: no uses etiquetas ambiguas o no explicadas. Si aparece un término técnico, defínelo brevemente en el mismo slide.
14. Cada slide debe dejar una idea cerrada y útil (qué es + por qué importa + dato concreto).
15. Cada body debe incluir al menos un dato verificable del tema (número, empresa, producto, organismo o fecha); evita hype sin evidencia.
16. No inventes datos fuera de los key points/contexto; si falta un dato, dilo sin fabricarlo.
17. Cada slide de contenido debe mapear al key point correspondiente en orden (slide 1 ↔ key point 1, etc.).

TONO: {tone_hint}
ESTILO: {style_hint}

Escribe SOLO el texto del prompt con los datos del tema embebidos.
Sin explicación y sin envolver en markdown."""

_DEFAULT_IMAGE_META = """Eres un/a Prompt Engineer para generación de imágenes con IA,
especializado/a en portadas virales de Instagram para una cuenta de noticias tech.

La imagen se usará en el 50% superior del cover del carrusel. El texto va en la mitad inferior.

TOPIC: {topic_en}

TU TAREA:
Crea un prompt que genere una imagen DIRECTAMENTE RELACIONADA con este tema.
NO caigas en "oficina genérica". Prioriza representación LITERAL del tema sobre metáforas abstractas.
Ejemplos:
- Tema gaming/consolas → setup gamer, mando, habitación con pantallas
- Tema IA → robot futurista, visualización de red neuronal, concepto de cerebro IA
- Tema hack/seguridad → figura encapuchada, glitches, pantalla rota
- Tema empresa → producto en uso, plano dramático del producto, entorno de trabajo
- Tema redes sociales → pantallas de smartphone, feeds, persona haciendo scroll
- Tema espacio/ciencia → astronauta, planeta, laboratorio con equipamiento

La imagen debe ser INMEDIATAMENTE reconocible como relacionada con "{topic_en}".

ESTILO:
- Ilustración SIMPLE y legible: composición minimalista, pocos elementos, lectura inmediata
- Ilustración editorial dibujada a mano, personal y expresiva (textura de pincel/tinta/lápiz visible)
- Acabado estilizado y humano (NO fotorrealista, NO render 3D, NO look de stock)
- Simbolismo temático fuerte y directamente conectado con el tema

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
- NO texto, letras, números ni palabras dentro de la imagen

Escribe un prompt corto (2-3 frases, máximo 100 palabras).
Escribe SOLO el prompt de generación de imagen. Sin explicación."""


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
            # Hard guardrail to keep subject placement stable for cover composition.
            crafted += (
                " Composition: single hero subject directly related to "
                f"'{topic_en}', dominant and in sharp focus in the upper half "
                "(top 45-55%); bottom 45% dark/clean negative space for text; "
                "no unrelated element may dominate the frame. "
                "Style must be hand-drawn editorial illustration with personal brush/ink texture, "
                "not photorealistic."
            )
            if cover_text:
                crafted += (
                    f" Headline hint: '{cover_text}'. Use a hero subject that matches "
                    "the concrete noun/context implied by this headline."
                )
            logger.info(f"Director crafted image prompt: {crafted[:80]}...")
            return crafted

        except Exception as e:
            logger.warning(f"Prompt Director failed for cover image: {e}")
            return None
