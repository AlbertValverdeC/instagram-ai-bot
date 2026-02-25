"""
Engagement strategy configuration.

Defines hashtags pools, posting schedules, and caption templates.
"""

# --- Posting Schedule ---
# Hours in 24h format, will be interpreted in the configured TIMEZONE
POSTING_HOURS = {
    "weekday_morning": "08:30",
    "weekday_evening": "18:30",
    "saturday": "10:00",
    "sunday": None,  # rest day
}

# Which slot to use by default (morning posts tend to perform well for tech)
DEFAULT_SLOT = "weekday_morning"

# --- Hashtag Pools ---
# The system picks from each category and rotates to avoid shadowban

HASHTAGS_HIGH_COMPETITION = [
    "#tecnologia", "#inteligenciaartificial", "#ia", "#tech", "#ai",
    "#technology", "#innovation", "#futuro", "#ciencia", "#digital",
]

HASHTAGS_MEDIUM_COMPETITION = [
    "#chatgpt", "#openai", "#machinelearning", "#deeplearning",
    "#datascience", "#robotica", "#automatizacion", "#bigdata",
    "#python", "#programacion", "#ciberseguridad", "#blockchain",
    "#realidadartificial", "#metaverso", "#nube", "#cloudcomputing",
    "#startups", "#emprendimiento", "#transformaciondigital", "#iot",
]

HASHTAGS_NICHE = [
    "#iaenespañol", "#techespañol", "#noticiastech", "#aprendetech",
    "#inteligenciaartificialenespañol", "#techlatam", "#ialatam",
    "#tecnologiaenespañol", "#futurotecnologico", "#mundodigital",
    "#techtips", "#techcommunity", "#learnai", "#aitools",
    "#techtrends",
]

# How many from each pool per post
HASHTAGS_DISTRIBUTION = {
    "high": 5,
    "medium": 15,
    "niche": 10,
}

# --- Caption Templates ---
# {topic} and {hook} are replaced dynamically
CAPTION_STRUCTURE = """
{hook}

{summary}

{cta_question}

·
·
·

{hashtags}
"""

CTA_PHRASES = [
    "Guarda este post para no olvidarlo 🔖",
    "Comparte con alguien que necesite saber esto 📲",
    "¿Qué opinas? Déjalo en los comentarios 👇",
    "Sígueme para más contenido de Tech e IA 🚀",
    "Dale like si aprendiste algo nuevo ❤️",
    "Guárdalo y compártelo con tu equipo 💡",
]

CTA_QUESTIONS = [
    "¿Ya conocías esta tecnología? 🤔",
    "¿Crees que esto cambiará el futuro? 💭",
    "¿Tú ya lo estás usando? Cuéntame 👇",
    "¿Qué tema quieres que cubra mañana? 📝",
    "¿Esto te parece una oportunidad o un riesgo? ⚡",
]
