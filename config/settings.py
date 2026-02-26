import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# --- Paths ---
ASSETS_DIR = PROJECT_ROOT / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
BACKGROUNDS_DIR = ASSETS_DIR / "backgrounds"
OUTPUT_DIR = PROJECT_ROOT / "output"
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
HISTORY_FILE = DATA_DIR / "history.json"
PROMPTS_DIR = DATA_DIR / "prompts"
DEFAULT_DB_PATH = DATA_DIR / "techtokio.db"

# Ensure directories exist
for d in [OUTPUT_DIR, DATA_DIR, LOGS_DIR, PROMPTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# --- API Keys ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "instagram-ai-bot/1.0")
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "")
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID", "")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
IMGUR_CLIENT_ID = os.getenv("IMGUR_CLIENT_ID", "")
GRAPH_API_VERSION = (os.getenv("GRAPH_API_VERSION", "v25.0") or "v25.0").strip()
PUBLIC_IMAGE_BASE_URL = os.getenv("PUBLIC_IMAGE_BASE_URL", "").strip().rstrip("/")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")
DUPLICATE_TOPIC_WINDOW_DAYS = int(os.getenv("DUPLICATE_TOPIC_WINDOW_DAYS", "90"))
IS_CLOUD_RUN = bool(os.getenv("K_SERVICE"))

# --- Instagram ---
INSTAGRAM_HANDLE = os.getenv("INSTAGRAM_HANDLE", "@tu_cuenta_tech")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Madrid")

# --- OpenAI ---
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_MAX_TOKENS = 2000
DIRECTOR_MODEL = os.getenv("DIRECTOR_MODEL", "gpt-4o")
CONTENT_USE_DIRECTOR = os.getenv("CONTENT_USE_DIRECTOR", "false").strip().lower() in {
    "1", "true", "yes", "on",
}

# --- Google AI (Imagen) ---
GOOGLE_AI_API_KEY = os.getenv("GOOGLE_AI_API_KEY", "")
GOOGLE_IMAGE_MODEL = os.getenv("GOOGLE_IMAGE_MODEL", "gemini-2.5-flash-image")

# --- Research ---
RESEARCH_CONFIG_FILE = DATA_DIR / "research_config.json"
RESEARCH_BACKEND = os.getenv("RESEARCH_BACKEND", "auto").strip().lower()
# Keep empty by default so focused topic search is not constrained to only tech outlets.
NEWSAPI_DOMAINS = ""
NEWSAPI_LANGUAGE = "en"
REDDIT_SUBREDDITS = ["artificial", "technology", "MachineLearning", "ChatGPT"]
RSS_FEEDS = [
    # High-signal general news (Spain + global)
    "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada",
    "https://e00-elmundo.uecdn.es/elmundo/rss/portada.xml",
    "https://www.eldiario.es/rss/",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    # Tech-focused feeds
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://feeds.arstechnica.com/arstechnica/index",
    "https://www.technologyreview.com/feed/",
]
TRENDS_KEYWORDS = [
    "AI", "GPT", "robot", "tech", "app", "Google", "Apple", "Meta",
    "Microsoft", "Samsung", "Tesla", "chip", "quantum", "cyber",
    "cloud", "data", "neural", "OpenAI", "startup", "software",
]

# --- Carousel ---
SLIDE_WIDTH = 1080
SLIDE_HEIGHT = 1350
NUM_CONTENT_SLIDES = 6  # + cover + CTA = 8 total
MAX_WORDS_PER_SLIDE = 40

# --- Profile Picture (for cover slide branding) ---
_profile_pic = ASSETS_DIR / "profile.png"
PROFILE_PIC_PATH = _profile_pic if _profile_pic.exists() else None

# --- Brand Logo (small badge on slides) ---
_brand_logo = ASSETS_DIR / "brand_logo.png"
BRAND_LOGO_PATH = _brand_logo if _brand_logo.exists() else PROFILE_PIC_PATH

# --- Logging ---
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
