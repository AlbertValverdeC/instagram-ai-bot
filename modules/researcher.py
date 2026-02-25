"""
Research module: finds trending Tech/AI topics from multiple sources.

Sources:
  - NewsAPI (newsapi.org)
  - RSS feeds (TechCrunch, The Verge, Ars Technica, MIT Tech Review)
  - Reddit (r/artificial, r/technology, r/MachineLearning, r/ChatGPT)
  - Google Trends (pytrends) for validation

Uses OpenAI to rank topics by relevance/virality and filters against history.
"""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import feedparser
import requests
from openai import OpenAI

from config.settings import (
    DATA_DIR,
    HISTORY_FILE,
    NEWSAPI_DOMAINS,
    NEWSAPI_KEY,
    NEWSAPI_LANGUAGE,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_SUBREDDITS,
    REDDIT_USER_AGENT,
    RESEARCH_CONFIG_FILE,
    RSS_FEEDS,
    TRENDS_KEYWORDS,
)
from modules.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


# ── Dynamic research config (editable via dashboard) ─────────────────────────

def _load_research_config() -> dict:
    """Load research config from JSON file, falling back to settings.py defaults."""
    defaults = {
        "subreddits": list(REDDIT_SUBREDDITS),
        "rss_feeds": list(RSS_FEEDS),
        "trends_keywords": list(TRENDS_KEYWORDS),
        "newsapi_domains": NEWSAPI_DOMAINS,
    }
    if RESEARCH_CONFIG_FILE.exists():
        try:
            with open(RESEARCH_CONFIG_FILE) as f:
                custom = json.load(f)
            # Merge: only override keys that exist in the custom file
            for key in defaults:
                if key in custom:
                    defaults[key] = custom[key]
            logger.info("Loaded custom research config from dashboard")
        except Exception as e:
            logger.warning(f"Failed to load research config: {e}. Using defaults.")
    return defaults


# ── Default fallback prompt (editable via dashboard) ─────────────────────────

_DEFAULT_RESEARCH_FALLBACK = """You are a social media content strategist for a Spanish-language Instagram account about Tech and AI.

Analyze these articles and select THE BEST topic for today's carousel post.

CRITERIA for selection:
1. High viral potential (surprising, impactful, or controversial)
2. Relevant to a broad tech-interested audience (not too niche)
3. Has enough substance for 6-8 carousel slides
4. NOT already covered (see past topics below)
5. Bonus if it aligns with current Google Trends

ARTICLES:
{articles_text}

GOOGLE TRENDS (tech-related):
{trends_text}

PAST TOPICS (avoid these):
{past_text}

Respond in this exact JSON format:
{{
    "topic": "Short topic title in Spanish (5-10 words)",
    "topic_en": "Same topic in English (for internal reference)",
    "why": "One sentence explaining why this topic is the best choice today",
    "key_points": [
        "Point 1: specific fact or data",
        "Point 2: specific fact or data",
        "Point 3: specific fact or data",
        "Point 4: specific fact or data",
        "Point 5: specific fact or data",
        "Point 6: specific fact or data"
    ],
    "source_urls": ["url1", "url2"],
    "virality_score": 8
}}

IMPORTANT: key_points should be in Spanish, concise, and include specific data (numbers, names, dates) when possible."""


def _load_history() -> list[dict]:
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return []


def _get_past_topics() -> set[str]:
    history = _load_history()
    return {entry.get("topic", "").lower() for entry in history}


# ── Source: NewsAPI ──────────────────────────────────────────────────────────

def fetch_newsapi() -> list[dict]:
    """Fetch top tech/AI headlines from NewsAPI."""
    if not NEWSAPI_KEY:
        logger.warning("NEWSAPI_KEY not set, skipping NewsAPI")
        return []

    config = _load_research_config()
    domains = config["newsapi_domains"]

    # Use /everything with domains if configured, otherwise /top-headlines
    if domains:
        url = "https://newsapi.org/v2/everything"
        params = {
            "apiKey": NEWSAPI_KEY,
            "domains": domains,
            "language": NEWSAPI_LANGUAGE,
            "sortBy": "publishedAt",
            "pageSize": 20,
        }
    else:
        url = "https://newsapi.org/v2/top-headlines"
        params = {
            "apiKey": NEWSAPI_KEY,
            "category": "technology",
            "language": NEWSAPI_LANGUAGE,
            "pageSize": 20,
        }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        articles = resp.json().get("articles", [])
        results = []
        for a in articles:
            results.append({
                "title": a.get("title", ""),
                "description": a.get("description", ""),
                "url": a.get("url", ""),
                "source": f"newsapi/{a.get('source', {}).get('name', 'unknown')}",
                "published": a.get("publishedAt", ""),
            })
        logger.info(f"NewsAPI returned {len(results)} articles")
        return results
    except Exception as e:
        logger.error(f"NewsAPI error: {e}")
        return []


# ── Source: RSS Feeds ────────────────────────────────────────────────────────

def fetch_rss() -> list[dict]:
    """Fetch recent articles from RSS feeds."""
    config = _load_research_config()
    results = []
    for feed_url in config["rss_feeds"]:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                results.append({
                    "title": entry.get("title", ""),
                    "description": entry.get("summary", "")[:300],
                    "url": entry.get("link", ""),
                    "source": f"rss/{feed.feed.get('title', feed_url)}",
                    "published": entry.get("published", ""),
                })
        except Exception as e:
            logger.error(f"RSS error for {feed_url}: {e}")
    logger.info(f"RSS feeds returned {len(results)} articles")
    return results


# ── Source: Reddit ───────────────────────────────────────────────────────────

def fetch_reddit() -> list[dict]:
    """Fetch hot posts from tech/AI subreddits using Reddit API."""
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        logger.warning("Reddit credentials not set, skipping Reddit")
        return []

    try:
        import praw

        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
        )
        config = _load_research_config()
        results = []
        for sub_name in config["subreddits"]:
            try:
                subreddit = reddit.subreddit(sub_name)
                for post in subreddit.hot(limit=10):
                    if post.stickied:
                        continue
                    results.append({
                        "title": post.title,
                        "description": (post.selftext or "")[:300],
                        "url": f"https://reddit.com{post.permalink}",
                        "source": f"reddit/r/{sub_name}",
                        "published": datetime.fromtimestamp(post.created_utc).isoformat(),
                        "score": post.score,
                    })
            except Exception as e:
                logger.error(f"Reddit error for r/{sub_name}: {e}")
        logger.info(f"Reddit returned {len(results)} posts")
        return results
    except ImportError:
        logger.warning("praw not installed, skipping Reddit")
        return []
    except Exception as e:
        logger.error(f"Reddit error: {e}")
        return []


# ── Source: Google Trends ────────────────────────────────────────────────────

def fetch_google_trends() -> list[str]:
    """Fetch trending tech-related searches from Google Trends."""
    try:
        from pytrends.request import TrendReq

        config = _load_research_config()
        pytrends = TrendReq(hl="es", tz=60)
        trending = pytrends.trending_searches(pn="spain")
        keywords = trending[0].tolist()[:20]
        # Filter to tech-ish keywords using dashboard-configurable list
        tech_keywords = config["trends_keywords"]
        filtered = [
            kw for kw in keywords
            if any(tk.lower() in kw.lower() for tk in tech_keywords)
        ]
        logger.info(f"Google Trends returned {len(filtered)} tech-related trends")
        return filtered
    except Exception as e:
        logger.error(f"Google Trends error: {e}")
        return []


# ── Topic Ranking with OpenAI ───────────────────────────────────────────────

def rank_topics(articles: list[dict], trends: list[str], past_topics: set[str]) -> dict:
    """Use OpenAI to select and summarize the best topic of the day."""
    if not articles:
        raise ValueError("No articles found from any source")

    # Prepare a condensed list for the LLM
    article_summaries = []
    for i, a in enumerate(articles[:40]):  # limit to 40 for token efficiency
        article_summaries.append(
            f"{i+1}. [{a['source']}] {a['title']}"
            + (f" — {a['description'][:150]}" if a.get("description") else "")
        )

    articles_text = "\n".join(article_summaries)
    trends_text = ", ".join(trends) if trends else "No Google Trends data available"
    past_text = ", ".join(list(past_topics)[:20]) if past_topics else "None"

    # Try Prompt Director for an optimized prompt
    director_prompt = None
    try:
        from modules.prompt_director import PromptDirector
        director = PromptDirector()
        director_prompt = director.craft_research_prompt(articles_text, trends_text, past_text)
    except Exception as e:
        logger.warning(f"Could not use Prompt Director for research: {e}")

    if director_prompt:
        prompt = director_prompt
        logger.info("Using director-crafted research prompt")
    else:
        logger.info("Using default research prompt")
        try:
            template = load_prompt("research_fallback", _DEFAULT_RESEARCH_FALLBACK)
            prompt = template.format(
                articles_text=articles_text,
                trends_text=trends_text,
                past_text=past_text,
            )
        except (KeyError, IndexError) as e:
            logger.warning(f"Custom research_fallback prompt error: {e}. Using default.")
            prompt = _DEFAULT_RESEARCH_FALLBACK.format(
                articles_text=articles_text,
                trends_text=trends_text,
                past_text=past_text,
            )

    client = OpenAI(api_key=OPENAI_API_KEY)

    def _call_openai(p):
        # OpenAI requires the word "json" in messages when using json_object format
        if "json" not in p.lower():
            p += "\n\nRespond in valid JSON format."
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": p}],
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)

    result = _call_openai(prompt)

    # Validate required keys — if director prompt produced wrong structure, retry with hardcoded
    required_keys = {"topic", "topic_en", "key_points"}
    if not required_keys.issubset(result.keys()):
        if director_prompt:
            logger.warning(f"Director prompt produced invalid keys: {list(result.keys())}. Retrying with default prompt.")
            fallback_prompt = _DEFAULT_RESEARCH_FALLBACK.format(
                articles_text=articles_text,
                trends_text=trends_text,
                past_text=past_text,
            )
            result = _call_openai(fallback_prompt)
        else:
            raise ValueError(f"OpenAI returned invalid JSON keys: {list(result.keys())}")

    logger.info(f"Selected topic: {result['topic']} (virality: {result.get('virality_score', '?')})")
    return result


# ── Main Entry Point ────────────────────────────────────────────────────────

def find_trending_topic() -> dict:
    """
    Main function: fetch from all sources, rank, and return the best topic.

    Returns a dict with keys: topic, topic_en, why, key_points, source_urls, virality_score
    """
    logger.info("Starting research phase...")
    past_topics = _get_past_topics()

    # Fetch from all sources in parallel
    all_articles = []
    trends = []

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(fetch_newsapi): "newsapi",
            executor.submit(fetch_rss): "rss",
            executor.submit(fetch_reddit): "reddit",
            executor.submit(fetch_google_trends): "trends",
        }

        for future in as_completed(futures):
            source = futures[future]
            try:
                result = future.result()
                if source == "trends":
                    trends = result
                else:
                    all_articles.extend(result)
            except Exception as e:
                logger.error(f"Error fetching {source}: {e}")

    logger.info(f"Total articles fetched: {len(all_articles)}, trends: {len(trends)}")

    if not all_articles:
        raise RuntimeError("No articles fetched from any source. Check API keys and network.")

    # Rank and select the best topic
    topic = rank_topics(all_articles, trends, past_topics)
    return topic


# ── CLI Test Mode ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    print("=" * 60)
    print("RESEARCHER MODULE — Test Mode")
    print("=" * 60)

    topic = find_trending_topic()
    print(f"\nSelected Topic: {topic['topic']}")
    print(f"English: {topic['topic_en']}")
    print(f"Why: {topic['why']}")
    print(f"Virality Score: {topic.get('virality_score', 'N/A')}")
    print(f"\nKey Points:")
    for i, point in enumerate(topic["key_points"], 1):
        print(f"  {i}. {point}")
    print(f"\nSources: {topic.get('source_urls', [])}")
