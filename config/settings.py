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

# Ensure directories exist
for d in [OUTPUT_DIR, DATA_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# --- API Keys ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "instagram-ai-bot/1.0")
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "")
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID", "")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
IMGUR_CLIENT_ID = os.getenv("IMGUR_CLIENT_ID", "")

# --- Instagram ---
INSTAGRAM_HANDLE = os.getenv("INSTAGRAM_HANDLE", "@tu_cuenta_tech")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Madrid")

# --- OpenAI ---
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_MAX_TOKENS = 2000

# --- Research ---
NEWSAPI_DOMAINS = "techcrunch.com,theverge.com,arstechnica.com,wired.com"
NEWSAPI_LANGUAGE = "en"
REDDIT_SUBREDDITS = ["artificial", "technology", "MachineLearning", "ChatGPT"]
RSS_FEEDS = [
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://feeds.arstechnica.com/arstechnica/index",
    "https://www.technologyreview.com/feed/",
]

# --- Carousel ---
SLIDE_WIDTH = 1080
SLIDE_HEIGHT = 1350
NUM_CONTENT_SLIDES = 6  # + cover + CTA = 8 total
MAX_WORDS_PER_SLIDE = 40

# --- Logging ---
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
