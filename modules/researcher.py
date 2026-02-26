"""
Research module: finds trending Tech/AI topics from multiple sources.

Sources:
  - Tavily News Search (optional primary backend)
  - NewsAPI (newsapi.org)
  - RSS feeds (TechCrunch, The Verge, Ars Technica, MIT Tech Review)
  - Reddit (r/artificial, r/technology, r/MachineLearning, r/ChatGPT)
  - Google Trends (pytrends) for validation

Uses OpenAI to rank topics by relevance/virality and filters against history.
"""

import json
import logging
import math
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus, urlparse

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
    RESEARCH_BACKEND,
    RESEARCH_CONFIG_FILE,
    RSS_FEEDS,
    TAVILY_API_KEY,
    TRENDS_KEYWORDS,
)
from modules.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

MAX_ARTICLE_AGE_DAYS = 30
MAX_FOCUS_ARTICLE_AGE_DAYS = 14
MIN_RECENT_ARTICLES = 8
MIN_FOCUS_FRESH_ARTICLES = 6
SOURCE_URL_LIMIT = 3
MAX_NEWS_QUERIES = 6
MAX_NEWS_PER_QUERY = 20
TAVILY_SEARCH_URL = "https://api.tavily.com/search"
TAVILY_MAX_QUERIES = 5
TAVILY_TOTAL_RESULTS = 40

# Curated domain quality priors for ranking and filtering.
HIGH_TRUST_DOMAINS = {
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "ft.com",
    "bloomberg.com",
    "wsj.com",
    "nytimes.com",
    "theguardian.com",
    "elpais.com",
    "elmundo.es",
    "lavanguardia.com",
    "abc.es",
    "elpais.com",
    "europapress.es",
    "rtve.es",
    "expansion.com",
    "eleconomista.es",
    "cincodias.elpais.com",
    "eldiario.es",
    "technologyreview.com",
    "techcrunch.com",
    "theverge.com",
    "arstechnica.com",
    "wired.com",
    "xataka.com",
    "genbeta.com",
    "forbes.com",
    "cnbc.com",
    "cnn.com",
}

MEDIUM_TRUST_DOMAINS = {
    "devex.com",
    "yahoo.com",
    "msn.com",
    "telegraph.co.uk",
    "nypost.com",
    "elconfidencial.com",
    "20minutos.es",
    "publico.es",
    "okdiario.com",
    "businessinsider.es",
    "lavozdegalicia.es",
    "cio.com",
}

BLOCKED_NEWS_DOMAINS = {
    "dignitymemorial.com",
    "legacy.com",
    "tributearchive.com",
}

GOOGLE_NEWS_SECTION_FEEDS = [
    ("google_news/top", "https://news.google.com/rss?hl=es&gl=ES&ceid=ES:es"),
    ("google_news/business", "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=es&gl=ES&ceid=ES:es"),
    ("google_news/technology", "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=es&gl=ES&ceid=ES:es"),
    ("google_news/world", "https://news.google.com/rss/headlines/section/topic/WORLD?hl=es&gl=ES&ceid=ES:es"),
]

_TOKEN_STOPWORDS = {
    "the",
    "and",
    "for",
    "from",
    "this",
    "that",
    "with",
    "your",
    "their",
    "will",
    "have",
    "about",
    "after",
    "before",
    "over",
    "under",
    "para",
    "como",
    "sobre",
    "entre",
    "cuando",
    "donde",
    "desde",
    "hasta",
    "tras",
    "ante",
    "pero",
    "mas",
    "muy",
    "este",
    "esta",
    "estos",
    "estas",
    "esas",
    "esos",
    "aqui",
    "alli",
    "tambien",
    "segun",
    "del",
    "que",
    "una",
    "uno",
    "unos",
    "unas",
    "los",
    "las",
    "por",
    "con",
    "sin",
    "año",
    "anos",
    "ano",
    "dia",
    "dias",
    "hoy",
    "ayer",
    "rtve",
    "elpais",
    "mundo",
    "espana",
    "para",
    "como",
}

_IRRELEVANT_TITLE_KEYWORDS = {
    "obituary",
    "memorial",
    "death notice",
    "funeral",
    "legacy.com",
}

_SHORT_KEEP_TOKENS = {
    "ia",
    "ai",
    "ml",
    "llm",
    "vr",
    "ar",
    "xr",
    "5g",
    "4g",
    "3d",
}

_AI_SIGNAL_TOKENS = {
    "ia",
    "ai",
    "llm",
    "gpt",
    "genai",
    "chatgpt",
    "openai",
    "gemini",
    "claude",
    "anthropic",
    "copilot",
    "perplexity",
    "deepseek",
}

_STORY_GENERIC_TOKENS = {
    "ia",
    "ai",
    "agente",
    "agentes",
    "inteligencia",
    "artificial",
    "tecnologia",
    "tecnologico",
    "tecnologica",
    "anuncia",
    "anuncian",
    "lanza",
    "lanzan",
    "presenta",
    "presentan",
    "nueva",
    "nuevo",
    "ultima",
    "hora",
    "hoy",
    "espana",
    "mexico",
    "colombia",
}

_TECH_SIGNAL_TOKENS = {
    "tecnologia",
    "tecnologico",
    "tecnologica",
    "tech",
    "software",
    "hardware",
    "startup",
    "startups",
    "app",
    "apps",
    "android",
    "ios",
    "iphone",
    "pixel",
    "galaxy",
    "samsung",
    "google",
    "microsoft",
    "apple",
    "meta",
    "openai",
    "gemini",
    "chatgpt",
    "claude",
    "copilot",
    "robot",
    "robots",
    "ia",
    "ai",
    "llm",
    "nube",
    "cloud",
}


def _normalize_focus_topic(focus_topic: str | None) -> str | None:
    """Normalize optional focus topic from user input."""
    if not focus_topic:
        return None
    focus_topic = focus_topic.strip()
    return focus_topic or None


def _matches_focus_topic(text: str, focus_topic: str | None) -> bool:
    """Return True when text strongly matches the focus topic intent."""
    if not focus_topic:
        return True
    text_norm = _normalize_text(text)
    topic_norm = _normalize_text(focus_topic)
    if topic_norm and topic_norm in text_norm:
        return True

    text_tokens = _tokenize(text)
    focus_tokens = _tokenize(focus_topic)
    if not focus_tokens:
        return False

    ai_focus = bool(focus_tokens.intersection({"ia", "ai"})) or "inteligencia artificial" in topic_norm
    non_ai_focus_tokens = {t for t in focus_tokens if t not in {"ia", "ai"}}
    overlap_non_ai = len(text_tokens.intersection(non_ai_focus_tokens))

    ai_text_signal = (
        bool(text_tokens.intersection(_AI_SIGNAL_TOKENS))
        or "inteligencia artificial" in text_norm
        or "artificial intelligence" in text_norm
    )

    if ai_focus:
        # For AI-focused queries, force explicit AI context + enough non-AI overlap.
        required_non_ai = 0
        if non_ai_focus_tokens:
            required_non_ai = max(1, math.ceil(len(non_ai_focus_tokens) * 0.6))
        return ai_text_signal and overlap_non_ai >= required_non_ai

    # Non-AI focus topics: require majority overlap for multi-word topics.
    if len(focus_tokens) == 1:
        return bool(text_tokens.intersection(focus_tokens))
    required = max(2, math.ceil(len(focus_tokens) * 0.6))
    return len(text_tokens.intersection(focus_tokens)) >= required


def _normalize_text(text: str) -> str:
    """Lowercase and remove accents for robust token matching."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", normalized.lower()).strip()


def _tokenize(text: str) -> set[str]:
    """Tokenize text using alphanumeric chunks and remove tiny/common words."""
    normalized = _normalize_text(text)
    tokens = {
        t for t in re.split(r"[^a-z0-9]+", normalized)
        if ((len(t) >= 3) or (len(t) == 2 and t in _SHORT_KEEP_TOKENS))
        and t not in _TOKEN_STOPWORDS
    }
    return tokens


def _parse_published_datetime(value: str) -> datetime | None:
    """Parse publication date from ISO/RFC822-like strings into UTC datetime."""
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None

    dt = None
    try:
        iso = raw.replace("Z", "+00:00") if raw.endswith("Z") else raw
        dt = datetime.fromisoformat(iso)
    except ValueError:
        try:
            dt = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            dt = None

    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _extract_domain(url: str) -> str:
    """Extract normalized domain (without www) from URL."""
    if not url:
        return ""
    try:
        domain = urlparse(url).netloc.lower()
    except Exception:
        return ""
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def _domain_matches(domain: str, patterns: set[str]) -> bool:
    """Return True if domain is exact match or subdomain of a known pattern."""
    if not domain:
        return False
    for pattern in patterns:
        if domain == pattern or domain.endswith(f".{pattern}"):
            return True
    return False


def _domain_trust_score(domain: str) -> float:
    """Return trust prior score for a domain."""
    if _domain_matches(domain, BLOCKED_NEWS_DOMAINS):
        return -5.0
    if _domain_matches(domain, HIGH_TRUST_DOMAINS):
        return 3.0
    if _domain_matches(domain, MEDIUM_TRUST_DOMAINS):
        return 1.0
    return -1.2


def _is_blocked_domain(domain: str) -> bool:
    """Return True for domains that should be ignored."""
    return _domain_matches(domain, BLOCKED_NEWS_DOMAINS)


def _build_focus_queries(focus_topic: str | None, query_hints: list[str] | None = None) -> list[str]:
    """Build query variants to improve recall while staying on-topic."""
    focus_topic = _normalize_focus_topic(focus_topic)
    if not focus_topic:
        return []

    focus_tokens = _tokenize(focus_topic)
    candidates: list[tuple[float, str]] = [
        (10.0, focus_topic),
        (9.0, f"\"{focus_topic}\""),
        (8.0, f"{focus_topic} última hora"),
    ]

    for hint in query_hints or []:
        clean = (hint or "").strip()
        if not clean or not _is_reasonable_query_hint(clean):
            continue
        hint_tokens = _tokenize(clean)
        overlap = len(focus_tokens.intersection(hint_tokens))
        if overlap == 0 and not _matches_focus_topic(clean, focus_topic):
            continue
        score = 4.0 + (overlap * 2.0)
        candidates.append((score, clean))
        candidates.append((score - 0.5, f"{focus_topic} {clean}"))

    seen = set()
    ordered: list[str] = []
    for _, query in sorted(candidates, key=lambda x: x[0], reverse=True):
        key = _normalize_text(query)
        if not key or key in seen:
            continue
        seen.add(key)
        ordered.append(query)
        if len(ordered) >= MAX_NEWS_QUERIES:
            break
    return ordered


def _resolve_research_backend() -> str:
    """
    Resolve research backend from env:
    - auto   -> tavily if API key exists, otherwise legacy
    - tavily -> tavily (fallback to legacy if key missing)
    - legacy -> existing multi-source stack
    """
    backend = (RESEARCH_BACKEND or "auto").strip().lower()
    if backend not in {"auto", "tavily", "legacy"}:
        logger.warning("Unknown RESEARCH_BACKEND '%s'. Using 'auto'.", backend)
        backend = "auto"

    if backend == "auto":
        return "tavily" if TAVILY_API_KEY else "legacy"

    if backend == "tavily" and not TAVILY_API_KEY:
        logger.warning("RESEARCH_BACKEND=tavily but TAVILY_API_KEY is missing. Falling back to legacy.")
        return "legacy"

    return backend


def _build_tavily_queries(focus_topic: str | None, trends: list[str] | None = None) -> list[str]:
    """Build Tavily queries: focused variants or broad tech radar queries."""
    focus_topic = _normalize_focus_topic(focus_topic)
    if focus_topic:
        return _build_focus_queries(focus_topic, query_hints=trends)[:TAVILY_MAX_QUERIES]

    candidates: list[str] = [
        "última hora tecnología inteligencia artificial apps gadgets",
        "tendencias tecnología hoy españa inteligencia artificial",
        "breaking technology news today ai apps gadgets",
    ]

    for trend in trends or []:
        hint = (trend or "").strip()
        if not hint or not _is_reasonable_query_hint(hint):
            continue
        candidates.append(f"tecnología {hint}")
        candidates.append(hint)

    seen = set()
    queries = []
    for query in candidates:
        key = _normalize_text(query)
        if not key or key in seen:
            continue
        seen.add(key)
        queries.append(query)
        if len(queries) >= TAVILY_MAX_QUERIES:
            break
    return queries


def _extract_headline_trends(headlines: list[str], limit: int = 20) -> list[str]:
    """Build lightweight trend terms from frequent headline tokens."""
    freq: dict[str, int] = {}
    for title in headlines:
        for token in _tokenize(title):
            if token.isdigit():
                continue
            freq[token] = freq.get(token, 0) + 1

    ranked = sorted(freq.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    return [token for token, _ in ranked[:limit]]


def _is_irrelevant_title(title: str) -> bool:
    """Filter obvious non-news matches when searching by person/topic."""
    normalized = _normalize_text(title)
    return any(keyword in normalized for keyword in _IRRELEVANT_TITLE_KEYWORDS)


def _dedupe_articles(articles: list[dict]) -> list[dict]:
    """Drop duplicate articles by URL/title while preserving order."""
    seen_urls = set()
    seen_titles = set()
    deduped = []

    for article in articles:
        url = (article.get("url") or "").strip()
        title_key = _normalize_text(article.get("title", ""))

        if url and url in seen_urls:
            continue
        if title_key and title_key in seen_titles:
            continue

        if url:
            seen_urls.add(url)
        if title_key:
            seen_titles.add(title_key)
        deduped.append(article)

    return deduped


def _filter_recent_articles(
    articles: list[dict],
    max_age_days: int = MAX_ARTICLE_AGE_DAYS,
) -> list[dict]:
    """Keep recent articles and gracefully backfill with undated ones when needed."""
    if not articles:
        return []

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max_age_days)
    recent = []
    stale = []
    undated = []

    for article in articles:
        published_dt = _parse_published_datetime(article.get("published", ""))
        if published_dt is None:
            undated.append(article)
            continue
        if published_dt >= cutoff:
            recent.append(article)
        else:
            stale.append(article)

    if stale:
        logger.info(f"Filtered out {len(stale)} stale articles older than {max_age_days} days")

    if len(recent) >= MIN_RECENT_ARTICLES:
        return recent
    if recent and undated:
        needed = MIN_RECENT_ARTICLES - len(recent)
        if needed > 0:
            logger.warning(
                "Only %s recent articles available; backfilling with %s undated items",
                len(recent),
                min(needed, len(undated)),
            )
            recent.extend(undated[:needed])
        return recent
    if recent:
        return recent
    if undated:
        logger.warning("No dated recent articles found; using undated items")
        return undated[:MIN_RECENT_ARTICLES]

    return []


def _filter_focus_freshness(
    articles: list[dict],
    focus_topic: str | None,
    max_age_days: int = MAX_FOCUS_ARTICLE_AGE_DAYS,
    min_keep: int = MIN_FOCUS_FRESH_ARTICLES,
) -> list[dict]:
    """
    For focused research, prefer truly recent coverage.
    Falls back if strict freshness would leave too little signal.
    """
    focus_topic = _normalize_focus_topic(focus_topic)
    if not focus_topic or not articles:
        return articles

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max_age_days)
    fresh = []
    for article in articles:
        published_dt = _parse_published_datetime(article.get("published", ""))
        if published_dt is None:
            continue
        if published_dt >= cutoff:
            fresh.append(article)

    if len(fresh) >= min_keep:
        logger.info(
            "Focus freshness filter kept %s/%s articles from the last %s days",
            len(fresh),
            len(articles),
            max_age_days,
        )
        return fresh

    logger.info(
        "Focus freshness filter skipped (only %s fresh articles, need >= %s)",
        len(fresh),
        min_keep,
    )
    return articles


def _article_hotness_score(article: dict, trends: list[str], focus_topic: str | None) -> float:
    """Score article by freshness, source trust, relevance and trend overlap."""
    score = 0.0
    now = datetime.now(timezone.utc)

    published_dt = _parse_published_datetime(article.get("published", ""))
    if published_dt is not None:
        age_hours = max(0.0, (now - published_dt).total_seconds() / 3600.0)
        if age_hours <= 6:
            score += 7.0
        elif age_hours <= 24:
            score += 5.5
        elif age_hours <= 48:
            score += 4.5
        elif age_hours <= 72:
            score += 3.2
        elif age_hours <= 7 * 24:
            score += 1.8
        elif age_hours <= 14 * 24:
            score += 0.6
        else:
            score -= 0.8
    else:
        score += 1.0

    domain = article.get("domain") or _extract_domain(article.get("url", ""))
    score += _domain_trust_score(domain)

    source = article.get("source", "")
    if source.startswith("google_news/"):
        score += 2.2
    elif source.startswith("tavily/"):
        score += 2.1
    elif source.startswith("newsapi/"):
        score += 2.0
    elif source.startswith("bing_news/"):
        score += 1.8
    elif source.startswith("rss/"):
        score += 1.6
    elif source.startswith("hn/"):
        score += 1.2
    elif source.startswith("reddit/"):
        score += 0.8

    text = f"{article.get('title', '')} {article.get('description', '')}"
    text_tokens = _tokenize(text)

    focus_tokens = _tokenize(focus_topic or "")
    if focus_tokens:
        score += len(text_tokens.intersection(focus_tokens)) * 1.8

    trend_tokens = set()
    for trend in (trends or [])[:20]:
        trend_tokens.update(_tokenize(trend))
    if trend_tokens:
        score += len(text_tokens.intersection(trend_tokens)) * 0.9

    return score


def _story_tokens(title: str, focus_topic: str | None) -> set[str]:
    """
    Extract story-specific title tokens to estimate cross-source consensus.
    """
    tokens = _tokenize(title)
    focus_tokens = _tokenize(focus_topic or "")
    if focus_tokens:
        tokens = {t for t in tokens if t not in focus_tokens}
    return {t for t in tokens if t not in _STORY_GENERIC_TOKENS}


def _apply_story_consensus_boost(scored: list[dict], focus_topic: str | None) -> list[dict]:
    """
    Boost stories corroborated across multiple domains and penalize isolated claims.
    """
    if not scored:
        return scored

    has_enough_pool = len(scored) >= 10
    for idx, article in enumerate(scored):
        tokens_i = _story_tokens(article.get("title", ""), focus_topic)
        if len(tokens_i) < 2:
            article["consensus_score"] = 0.0
            continue

        corroborating_domains = set()
        match_count = 0
        for jdx, other in enumerate(scored):
            if idx == jdx:
                continue
            tokens_j = _story_tokens(other.get("title", ""), focus_topic)
            if len(tokens_j) < 2:
                continue
            overlap = len(tokens_i.intersection(tokens_j))
            if overlap >= 2:
                other_domain = other.get("domain") or "unknown"
                if other_domain and other_domain != article.get("domain"):
                    corroborating_domains.add(other_domain)
                match_count += 1

        corroboration = len(corroborating_domains)
        boost = min(4.5, (corroboration * 0.9) + (match_count * 0.2))

        # In focused mode with enough candidates, distrust one-off claims.
        if focus_topic and has_enough_pool:
            if corroboration == 0:
                boost -= 1.6
            elif corroboration == 1:
                boost -= 0.6

        article["consensus_score"] = round(boost, 3)
        article["hot_score"] = round(article.get("hot_score", 0.0) + boost, 3)

    return scored


def _prioritize_articles(
    articles: list[dict],
    trends: list[str],
    focus_topic: str | None = None,
    limit: int = 60,
    max_per_domain: int = 4,
) -> list[dict]:
    """
    Rank articles by hotness and keep diversity across domains.
    """
    if not articles:
        return []

    scored = []
    for article in articles:
        domain = article.get("domain") or _extract_domain(article.get("url", ""))
        if _is_blocked_domain(domain):
            continue
        enriched = dict(article)
        enriched["domain"] = domain
        enriched["hot_score"] = round(_article_hotness_score(enriched, trends, focus_topic), 3)
        scored.append(enriched)

    scored = _apply_story_consensus_boost(scored, focus_topic)

    scored.sort(
        key=lambda a: (
            a.get("hot_score", 0.0),
            (_parse_published_datetime(a.get("published", "")) or datetime.min.replace(tzinfo=timezone.utc)),
        ),
        reverse=True,
    )

    diversified = []
    domain_counts: dict[str, int] = {}
    for article in scored:
        domain = article.get("domain") or "unknown"
        count = domain_counts.get(domain, 0)
        if domain and count >= max_per_domain:
            continue
        domain_counts[domain] = count + 1
        diversified.append(article)
        if len(diversified) >= limit:
            break

    return diversified


def _strict_focus_filter(articles: list[dict], focus_topic: str | None) -> list[dict]:
    """Re-apply strict focus filtering across all sources as a final guardrail."""
    focus_topic = _normalize_focus_topic(focus_topic)
    if not focus_topic or not articles:
        return articles

    filtered = []
    for article in articles:
        combined = f"{article.get('title', '')} {article.get('description', '')}"
        if _matches_focus_topic(combined, focus_topic):
            filtered.append(article)

    removed = len(articles) - len(filtered)
    if removed > 0:
        logger.info("Strict focus filter removed %s off-topic articles", removed)

    # Avoid complete collapse if source quality is very poor.
    return filtered if filtered else articles


def _filter_low_trust_focus_articles(
    articles: list[dict],
    focus_topic: str | None,
    min_trust_score: float = 0.0,
) -> list[dict]:
    """
    When enough coverage exists, drop low-trust domains for focused research.
    Keeps broader recall if this would remove too much.
    """
    focus_topic = _normalize_focus_topic(focus_topic)
    if not focus_topic or not articles:
        return articles

    trusted = []
    for article in articles:
        domain = article.get("domain") or _extract_domain(article.get("url", ""))
        if _domain_trust_score(domain) >= min_trust_score:
            trusted.append(article)

    # Apply when we can still preserve a minimum of source diversity.
    min_keep = max(4, min(10, len(articles) // 8))
    if len(trusted) >= min_keep:
        logger.info(
            "Focus quality filter kept %s/%s articles from neutral/high-trust domains",
            len(trusted),
            len(articles),
        )
        return trusted

    logger.info(
        "Focus quality filter skipped (insufficient trusted coverage: %s/%s)",
        len(trusted),
        len(articles),
    )
    return articles


def _log_top_articles(articles: list[dict], top_n: int = 10):
    """Log top-ranked articles for observability."""
    for idx, article in enumerate(articles[:top_n], 1):
        logger.info(
            "Top %s | hot=%.2f | consensus=%.2f | %s | %s | %s",
            idx,
            article.get("hot_score", 0.0),
            article.get("consensus_score", 0.0),
            article.get("domain", "unknown"),
            article.get("published", "unknown-date"),
            article.get("title", "")[:140],
        )


def _score_source_match(article: dict, topic_tokens: set[str], focus_tokens: set[str]) -> tuple[float, float]:
    """Score candidate source URLs by textual relevance and recency."""
    title = article.get("title", "")
    description = article.get("description", "")
    text_tokens = _tokenize(f"{title} {description}")

    topic_overlap = len(topic_tokens.intersection(text_tokens))
    focus_overlap = len(focus_tokens.intersection(text_tokens))
    score = (topic_overlap * 3.0) + (focus_overlap * 2.0)

    published_dt = _parse_published_datetime(article.get("published", ""))
    freshness_ts = 0.0
    if published_dt is not None:
        freshness_ts = published_dt.timestamp()
        age_days = max(0, (datetime.now(timezone.utc) - published_dt).days)
        score += max(0.0, 4.0 - (age_days / 5.0))

    if article.get("source", "").startswith(("newsapi/", "rss/", "google_news/", "tavily/")):
        score += 0.5

    domain = article.get("domain") or _extract_domain(article.get("url", ""))
    if _is_blocked_domain(domain):
        score -= 20.0
    else:
        score += _domain_trust_score(domain) * 1.6

    return score, freshness_ts


def _pick_source_urls(
    articles: list[dict],
    selected_topic: str,
    focus_topic: str | None = None,
    limit: int = SOURCE_URL_LIMIT,
) -> list[str]:
    """Choose real source URLs from fetched articles, favoring relevance + freshness."""
    topic_tokens = _tokenize(selected_topic)
    focus_tokens = _tokenize(focus_topic or "")
    scored = []

    for article in articles:
        url = (article.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            continue
        score, freshness_ts = _score_source_match(article, topic_tokens, focus_tokens)
        domain = article.get("domain") or _extract_domain(url)
        scored.append({
            "url": url,
            "score": score,
            "freshness_ts": freshness_ts,
            "domain": domain,
        })

    scored.sort(key=lambda x: (x["score"], x["freshness_ts"]), reverse=True)

    selected = []
    used_domains = set()
    for candidate in scored:
        if candidate["domain"] and candidate["domain"] in used_domains:
            continue
        selected.append(candidate["url"])
        if candidate["domain"]:
            used_domains.add(candidate["domain"])
        if len(selected) >= limit:
            break

    if len(selected) < limit:
        for candidate in scored:
            if candidate["url"] in selected:
                continue
            selected.append(candidate["url"])
            if len(selected) >= limit:
                break

    return selected[:limit]


def _sanitize_research_text(text: str) -> str:
    """Normalize spacing/punctuation in model-generated research strings."""
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    clean = re.sub(r"\s+([,.;:!?])", r"\1", clean)
    clean = re.sub(r"([¿¡])\s+", r"\1", clean)
    return clean


def _clarify_key_point(point: str) -> str:
    """Light cleanup for model-generated key points."""
    p = _sanitize_research_text(point)
    p = re.sub(r"[\"'“”‘’]+", "", p)
    return p


def _is_reasonable_query_hint(hint: str) -> bool:
    """Discard noisy query hints from Trends that are not valid search terms."""
    h = _normalize_text(hint)
    if not h:
        return False
    if len(h) > 80 or len(h.split()) > 8:
        return False
    if "http" in h:
        return False
    if "not available" in h or "please upgrade" in h:
        return False
    return True


def _is_generic_tech_article(article: dict, tech_keywords: list[str]) -> bool:
    """Return True when article text has clear tech/AI signal."""
    text = f"{article.get('title', '')} {article.get('description', '')} {article.get('source_name', '')}"
    norm = _normalize_text(text)
    tokens = _tokenize(text)

    if tokens.intersection(_AI_SIGNAL_TOKENS) or tokens.intersection(_TECH_SIGNAL_TOKENS):
        return True

    for kw in tech_keywords or []:
        k = _normalize_text(str(kw))
        if not k or len(k) < 3:
            continue
        if len(k.split()) > 4:
            continue
        if k in norm:
            return True
    return False


def _filter_generic_tech_articles(articles: list[dict], tech_keywords: list[str]) -> list[dict]:
    """
    In generic mode (no focus topic), keep the pool centered on tech/AI news.
    """
    if not articles:
        return articles

    filtered = [a for a in articles if _is_generic_tech_article(a, tech_keywords)]
    min_keep = max(12, len(articles) // 10)
    if len(filtered) >= min_keep:
        removed = len(articles) - len(filtered)
        if removed > 0:
            logger.info("Generic tech filter removed %s non-tech articles", removed)
        return filtered

    logger.info(
        "Generic tech filter skipped (insufficient tech coverage: %s/%s)",
        len(filtered),
        len(articles),
    )
    return articles


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

_DEFAULT_RESEARCH_FALLBACK = """Eres estratega de contenido para una cuenta de Instagram en español sobre Tech e IA.

La marca es "TechTokio ⚡ 30s": radar diario de tecnología con aura Neo-Tokio.
Tono de marca: directo, afilado, con humor inteligente y siempre sin humo.

Analiza los artículos y selecciona EL MEJOR tema para el carrusel de hoy.

CRITERIOS:
1. Debe ser claramente tech/IA/apps/gadgets/tendencias digitales.
2. Debe estar reciente y con conversación real (mejor si aparece en varios medios).
3. Debe permitir explicar valor real en 6 key points, sin dejar dudas.
4. Debe ser entendible rápido: útil para una pieza "30 segundos".
5. No repetir temas recientes.
6. Evitar humo, titulares vacíos o afirmaciones no verificables.

ARTÍCULOS:
{articles_text}

GOOGLE TRENDS (relacionado con tech):
{trends_text}

TEMAS PASADOS (evitar):
{past_text}

Responde en este formato JSON exacto:
{{
    "topic": "Título corto del tema en español (5-10 palabras)",
    "topic_en": "Mismo tema en inglés (referencia interna)",
    "why": "Una frase explicando por qué este es el mejor tema hoy",
    "key_points": [
        "Punto 1: dato o hecho específico",
        "Punto 2: dato o hecho específico",
        "Punto 3: dato o hecho específico",
        "Punto 4: dato o hecho específico",
        "Punto 5: dato o hecho específico",
        "Punto 6: dato o hecho específico"
    ],
    "source_urls": ["url1", "url2"],
    "virality_score": 8
}}

IMPORTANTE:
- Resume solo lo que aparece en las fuentes.
- No inventes hechos, cifras ni contexto.
- Mantén el alcance exacto de la noticia (si es actualización, dilo como actualización).
- Cada key_point debe ser autocontenido y entendible sin leer el artículo completo."""


def _load_history() -> list[dict]:
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return []


def _get_past_topics() -> set[str]:
    history = _load_history()
    return {entry.get("topic", "").lower() for entry in history}


# ── Source: NewsAPI ──────────────────────────────────────────────────────────

def _normalize_tavily_result(
    item: dict,
    query: str,
    focus_topic: str | None = None,
) -> dict | None:
    """Convert one Tavily result to normalized article shape."""
    title = (item.get("title") or "").strip()
    url = (item.get("url") or "").strip()
    if not title or not url:
        return None
    if _is_irrelevant_title(title):
        return None

    description = (
        (item.get("content") or "")
        or (item.get("raw_content") or "")
        or (item.get("snippet") or "")
    ).strip()
    combined = f"{title} {description}"
    if focus_topic and not _matches_focus_topic(combined, focus_topic):
        return None

    domain = _extract_domain(url)
    if _is_blocked_domain(domain):
        return None

    published = (
        item.get("published_date")
        or item.get("published")
        or item.get("date")
        or ""
    )

    score = item.get("score", 0.0)
    try:
        relevance_score = float(score)
    except (TypeError, ValueError):
        relevance_score = 0.0

    return {
        "title": title,
        "description": description[:300],
        "url": url,
        "source": "tavily/news",
        "published": published,
        "domain": domain,
        "query": query,
        "relevance_score": round(relevance_score, 4),
    }


def fetch_tavily_news(
    focus_topic: str | None = None,
    query_hints: list[str] | None = None,
) -> list[dict]:
    """
    Fetch recent web news from Tavily.
    Uses broad queries in generic mode and strict variants in focused mode.
    """
    if not TAVILY_API_KEY:
        logger.warning("TAVILY_API_KEY not set, skipping Tavily")
        return []

    focus_topic = _normalize_focus_topic(focus_topic)
    queries = _build_tavily_queries(focus_topic, trends=query_hints)
    if not queries:
        return []

    per_query_limit = max(6, min(15, math.ceil(TAVILY_TOTAL_RESULTS / max(1, len(queries)))))
    results = []
    per_query_counts: dict[str, int] = {}

    for query in queries:
        payload = {
            "api_key": TAVILY_API_KEY,
            "query": query,
            "topic": "news",
            "search_depth": "advanced",
            "max_results": per_query_limit,
            "include_raw_content": False,
        }
        try:
            resp = requests.post(TAVILY_SEARCH_URL, json=payload, timeout=25)
            resp.raise_for_status()
            raw_results = (resp.json() or {}).get("results", []) or []
        except Exception as e:
            logger.error("Tavily error for query '%s': %s", query, e)
            per_query_counts[query] = 0
            continue

        kept = 0
        for item in raw_results:
            parsed = _normalize_tavily_result(item, query=query, focus_topic=focus_topic)
            if not parsed:
                continue
            results.append(parsed)
            kept += 1
        per_query_counts[query] = kept

    results = _dedupe_articles(results)
    logger.info(
        "Tavily returned %s deduped articles for topic '%s' across %s queries (%s)",
        len(results),
        focus_topic,
        len(queries),
        ", ".join(f"{q}:{c}" for q, c in per_query_counts.items()),
    )
    return results


# ── Source: NewsAPI ──────────────────────────────────────────────────────────

def fetch_newsapi(focus_topic: str | None = None) -> list[dict]:
    """Fetch top tech/AI headlines from NewsAPI, optionally focused on a topic."""
    if not NEWSAPI_KEY:
        logger.warning("NEWSAPI_KEY not set, skipping NewsAPI")
        return []

    focus_topic = _normalize_focus_topic(focus_topic)
    config = _load_research_config()
    domains = config["newsapi_domains"]

    # Focused mode: search recent articles for the topic
    if focus_topic:
        url = "https://newsapi.org/v2/everything"
        params = {
            "apiKey": NEWSAPI_KEY,
            "q": focus_topic,
            "language": NEWSAPI_LANGUAGE,
            "sortBy": "publishedAt",
            "pageSize": 30,
            "from": (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        if domains:
            params["domains"] = domains
    # Generic mode: use /everything with domains if configured, otherwise /top-headlines
    elif domains:
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
            url = a.get("url", "")
            domain = _extract_domain(url)
            if _is_blocked_domain(domain):
                continue
            results.append({
                "title": a.get("title", ""),
                "description": a.get("description", ""),
                "url": url,
                "source": f"newsapi/{a.get('source', {}).get('name', 'unknown')}",
                "published": a.get("publishedAt", ""),
                "domain": domain,
            })
        if focus_topic:
            logger.info(f"NewsAPI returned {len(results)} articles for topic '{focus_topic}'")
        else:
            logger.info(f"NewsAPI returned {len(results)} articles")
        return results
    except Exception as e:
        logger.error(f"NewsAPI error: {e}")
        return []


# ── Source: RSS Feeds ────────────────────────────────────────────────────────

def fetch_rss(focus_topic: str | None = None) -> list[dict]:
    """Fetch recent articles from RSS feeds, optionally filtered by topic."""
    focus_topic = _normalize_focus_topic(focus_topic)
    config = _load_research_config()
    results = []
    for feed_url in config["rss_feeds"]:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:20]:
                title = entry.get("title", "")
                summary = entry.get("summary", "")[:300]
                combined = f"{title} {summary}"
                if focus_topic and not _matches_focus_topic(combined, focus_topic):
                    continue
                url = entry.get("link", "")
                domain = _extract_domain(url)
                if _is_blocked_domain(domain):
                    continue
                results.append({
                    "title": title,
                    "description": summary,
                    "url": url,
                    "source": f"rss/{feed.feed.get('title', feed_url)}",
                    "published": entry.get("published", ""),
                    "domain": domain,
                })
        except Exception as e:
            logger.error(f"RSS error for {feed_url}: {e}")
    if focus_topic:
        logger.info(f"RSS feeds returned {len(results)} articles for topic '{focus_topic}'")
    else:
        logger.info(f"RSS feeds returned {len(results)} articles")
    return results


# ── Source: Google News RSS (topic search, no API key) ──────────────────────

def _parse_google_news_entry(entry, source_label: str, focus_topic: str | None = None) -> dict | None:
    """Convert one Google News RSS entry into normalized article dict."""
    title = entry.get("title", "")
    if not title or _is_irrelevant_title(title):
        return None

    summary = entry.get("summary", "")[:300]
    combined = f"{title} {summary}"
    if focus_topic and not _matches_focus_topic(combined, focus_topic):
        return None

    source_meta = entry.get("source", {}) or {}
    source_homepage = source_meta.get("href", "")
    link = entry.get("link", "")
    domain = _extract_domain(source_homepage) or _extract_domain(link)
    if _is_blocked_domain(domain):
        return None

    return {
        "title": title,
        "description": summary,
        "url": link,
        "source": source_label,
        "source_name": source_meta.get("title", ""),
        "source_homepage": source_homepage,
        "published": entry.get("published", ""),
        "domain": domain,
    }


def fetch_google_news_rss(
    focus_topic: str | None = None,
    query_hints: list[str] | None = None,
) -> list[dict]:
    """
    Fetch topic-focused news from Google News RSS using query expansion.

    This source is free and tends to capture very recent stories.
    """
    queries = _build_focus_queries(focus_topic, query_hints)
    if not queries:
        return []

    results = []
    per_query_counts = {}
    try:
        for query_text in queries:
            query = quote_plus(query_text)
            feed_url = (
                "https://news.google.com/rss/search?"
                f"q={query}&hl=es&gl=ES&ceid=ES:es"
            )
            feed = feedparser.parse(feed_url)
            count = 0
            for entry in feed.entries[:MAX_NEWS_PER_QUERY]:
                parsed = _parse_google_news_entry(entry, "google_news/rss_search", focus_topic=focus_topic)
                if not parsed:
                    continue
                parsed["query"] = query_text
                results.append(parsed)
                count += 1
            per_query_counts[query_text] = count

        results = _dedupe_articles(results)
        logger.info(
            "Google News RSS (search) returned %s deduped articles for topic '%s' across %s queries (%s)",
            len(results),
            focus_topic,
            len(queries),
            ", ".join(f"{q}:{c}" for q, c in per_query_counts.items()),
        )
        return results
    except Exception as e:
        logger.error(f"Google News RSS error: {e}")
        return results


def fetch_google_news_sections(focus_topic: str | None = None) -> list[dict]:
    """
    Fetch hot stories from Google News sections and filter by focus topic.
    """
    focus_topic = _normalize_focus_topic(focus_topic)

    results = []
    try:
        for source_label, feed_url in GOOGLE_NEWS_SECTION_FEEDS:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:MAX_NEWS_PER_QUERY]:
                parsed = _parse_google_news_entry(entry, source_label, focus_topic=focus_topic)
                if parsed:
                    results.append(parsed)
        results = _dedupe_articles(results)
        logger.info(
            "Google News section feeds returned %s deduped articles for topic '%s'",
            len(results),
            focus_topic,
        )
        return results
    except Exception as e:
        logger.error(f"Google News section feeds error: {e}")
        return results


def fetch_bing_news_rss(
    focus_topic: str | None = None,
    query_hints: list[str] | None = None,
) -> list[dict]:
    """Fetch focused news from Bing News RSS as an extra aggregator signal."""
    queries = _build_focus_queries(focus_topic, query_hints)
    if not queries:
        return []

    results = []
    per_query_counts = {}
    try:
        for query_text in queries:
            query = quote_plus(query_text)
            feed_url = f"https://www.bing.com/news/search?q={query}&format=rss&mkt=es-ES"
            feed = feedparser.parse(feed_url)
            count = 0
            for entry in feed.entries[:MAX_NEWS_PER_QUERY]:
                title = entry.get("title", "")
                if not title or _is_irrelevant_title(title):
                    continue
                summary = entry.get("summary", "")[:300]
                combined = f"{title} {summary}"
                if focus_topic and not _matches_focus_topic(combined, focus_topic):
                    continue
                link = entry.get("link", "")
                domain = _extract_domain(link)
                if _is_blocked_domain(domain):
                    continue
                results.append({
                    "title": title,
                    "description": summary,
                    "url": link,
                    "source": "bing_news/rss",
                    "published": entry.get("published", ""),
                    "domain": domain,
                    "query": query_text,
                })
                count += 1
            per_query_counts[query_text] = count

        results = _dedupe_articles(results)
        logger.info(
            "Bing News RSS returned %s deduped articles for topic '%s' across %s queries (%s)",
            len(results),
            focus_topic,
            len(queries),
            ", ".join(f"{q}:{c}" for q, c in per_query_counts.items()),
        )
        return results
    except Exception as e:
        logger.error(f"Bing News RSS error: {e}")
        return results


# ── Source: Reddit ───────────────────────────────────────────────────────────

def fetch_reddit(focus_topic: str | None = None) -> list[dict]:
    """Fetch Reddit posts from configured subreddits, optionally focused on a topic."""
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        logger.warning("Reddit credentials not set, using public Reddit JSON fallback")
        return fetch_reddit_public(focus_topic=focus_topic)

    focus_topic = _normalize_focus_topic(focus_topic)

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
                if focus_topic:
                    posts_iter = subreddit.search(
                        query=focus_topic,
                        sort="new",
                        time_filter="week",
                        limit=15,
                    )
                else:
                    posts_iter = subreddit.hot(limit=10)

                for post in posts_iter:
                    if post.stickied:
                        continue
                    if focus_topic and not _matches_focus_topic(
                        f"{post.title} {post.selftext or ''}",
                        focus_topic,
                    ):
                        continue
                    url = f"https://reddit.com{post.permalink}"
                    results.append({
                        "title": post.title,
                        "description": (post.selftext or "")[:300],
                        "url": url,
                        "source": f"reddit/r/{sub_name}",
                        "published": datetime.fromtimestamp(post.created_utc).isoformat(),
                        "score": post.score,
                        "domain": _extract_domain(url),
                    })
            except Exception as e:
                logger.error(f"Reddit error for r/{sub_name}: {e}")
        if focus_topic:
            logger.info(f"Reddit returned {len(results)} posts for topic '{focus_topic}'")
        else:
            logger.info(f"Reddit returned {len(results)} posts")
        return results
    except ImportError:
        logger.warning("praw not installed, skipping Reddit")
        return []
    except Exception as e:
        logger.error(f"Reddit error: {e}")
        return fetch_reddit_public(focus_topic=focus_topic)


def fetch_reddit_public(focus_topic: str | None = None) -> list[dict]:
    """
    Fallback Reddit source using public JSON endpoints (no OAuth credentials).
    """
    focus_topic = _normalize_focus_topic(focus_topic)
    config = _load_research_config()
    results = []
    headers = {"User-Agent": REDDIT_USER_AGENT or "instagram-ai-bot/1.0"}

    for sub_name in config["subreddits"]:
        try:
            url = f"https://www.reddit.com/r/{sub_name}/hot.json?limit=20"
            resp = requests.get(url, headers=headers, timeout=12)
            resp.raise_for_status()
            posts = (resp.json() or {}).get("data", {}).get("children", [])
            for row in posts:
                data = row.get("data", {})
                if not data:
                    continue
                title = data.get("title", "")
                body = (data.get("selftext") or "")[:300]
                if not title:
                    continue
                if focus_topic and not _matches_focus_topic(f"{title} {body}", focus_topic):
                    continue
                created_utc = data.get("created_utc")
                published = ""
                if created_utc:
                    published = datetime.utcfromtimestamp(created_utc).isoformat() + "Z"
                permalink = data.get("permalink", "")
                link = f"https://reddit.com{permalink}" if permalink else ""
                results.append({
                    "title": title,
                    "description": body,
                    "url": link,
                    "source": f"reddit_public/r/{sub_name}",
                    "published": published,
                    "score": data.get("score", 0),
                    "domain": "reddit.com",
                })
        except Exception as e:
            logger.error(f"Public Reddit error for r/{sub_name}: {e}")

    if focus_topic:
        logger.info(f"Public Reddit returned {len(results)} posts for topic '{focus_topic}'")
    else:
        logger.info(f"Public Reddit returned {len(results)} posts")
    return results


# ── Source: Hacker News ──────────────────────────────────────────────────────

def fetch_hackernews(focus_topic: str | None = None) -> list[dict]:
    """
    Fetch top stories from Hacker News.

    This source requires no API key and is useful for current tech momentum.
    """
    focus_topic = _normalize_focus_topic(focus_topic)
    try:
        ids_resp = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            timeout=12,
        )
        ids_resp.raise_for_status()
        story_ids = ids_resp.json()[:120]

        results = []
        for story_id in story_ids:
            item_resp = requests.get(
                f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                timeout=12,
            )
            item_resp.raise_for_status()
            item = item_resp.json() or {}
            if item.get("type") != "story":
                continue

            title = item.get("title", "")
            if not title:
                continue
            if focus_topic and not _matches_focus_topic(title, focus_topic):
                continue

            ts = item.get("time")
            published = ""
            if ts:
                published = datetime.utcfromtimestamp(ts).isoformat() + "Z"
            url = item.get("url", f"https://news.ycombinator.com/item?id={item.get('id', '')}")
            domain = _extract_domain(url)
            if _is_blocked_domain(domain):
                continue

            results.append({
                "title": title,
                "description": "",
                "url": url,
                "source": "hn/topstories",
                "published": published,
                "score": item.get("score", 0),
                "domain": domain,
            })

            # Keep this source lightweight
            if len(results) >= 25:
                break

        if focus_topic:
            logger.info(f"Hacker News returned {len(results)} stories for topic '{focus_topic}'")
        else:
            logger.info(f"Hacker News returned {len(results)} stories")
        return results
    except Exception as e:
        logger.error(f"Hacker News error: {e}")
        return []


# ── Source: Google Trends ────────────────────────────────────────────────────

def fetch_google_trends(focus_topic: str | None = None) -> list[str]:
    """Fetch trends from Google Trends, generic or focused by topic."""
    focus_topic = _normalize_focus_topic(focus_topic)
    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="es", tz=60)

        if focus_topic:
            trends = []

            try:
                pytrends.build_payload([focus_topic], timeframe="now 7-d")
                related = pytrends.related_queries().get(focus_topic, {})
                for section in ("rising", "top"):
                    df = related.get(section)
                    if df is not None and "query" in df.columns:
                        trends.extend(df["query"].head(10).tolist())
            except Exception as e:
                logger.warning(f"Google Trends related_queries failed for '{focus_topic}': {e}")

            try:
                suggestions = pytrends.suggestions(keyword=focus_topic)
                for row in suggestions[:10]:
                    title = row.get("title")
                    if title:
                        trends.append(title)
            except Exception as e:
                logger.warning(f"Google Trends suggestions failed for '{focus_topic}': {e}")

            # Deduplicate while preserving order
            seen = set()
            deduped = []
            for trend in trends:
                key = trend.strip().lower()
                if key and key not in seen:
                    seen.add(key)
                    deduped.append(trend.strip())

            logger.info(f"Google Trends returned {len(deduped)} focused trends for '{focus_topic}'")
            return deduped[:20]

        config = _load_research_config()
        trending = None
        for geo in ("spain", "united_states"):
            try:
                trending = pytrends.trending_searches(pn=geo)
                if trending is not None and not trending.empty:
                    break
            except Exception as e:
                logger.warning(f"Google Trends trending_searches failed for '{geo}': {e}")
                trending = None

        if trending is None or trending.empty:
            logger.warning("Google Trends generic trending_searches unavailable; using Google News headline fallback")
            try:
                top_feed = feedparser.parse(GOOGLE_NEWS_SECTION_FEEDS[0][1])
                titles = [e.get("title", "") for e in top_feed.entries[:80] if e.get("title")]
                fallback_trends = _extract_headline_trends(titles, limit=20)
                logger.info(f"Headline fallback produced {len(fallback_trends)} trend terms")
                return fallback_trends
            except Exception as e:
                logger.warning(f"Headline fallback failed: {e}")
                return []

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

def rank_topics(
    articles: list[dict],
    trends: list[str],
    past_topics: set[str],
    focus_topic: str | None = None,
) -> dict:
    """Use OpenAI to select and summarize the best topic of the day."""
    if not articles:
        raise ValueError("No articles found from any source")

    focus_topic = _normalize_focus_topic(focus_topic)

    # Prepare a condensed list for the LLM
    article_summaries = []
    for i, a in enumerate(articles[:40]):  # limit to 40 for token efficiency
        published_dt = _parse_published_datetime(a.get("published", ""))
        published_label = published_dt.strftime("%Y-%m-%d") if published_dt else "unknown-date"
        hot_score = a.get("hot_score")
        score_label = f"{hot_score:.2f}" if isinstance(hot_score, (int, float)) else "n/a"
        domain = a.get("domain") or _extract_domain(a.get("url", ""))
        article_summaries.append(
            f"{i+1}. [{a['source']} | {domain} | {published_label} | hot={score_label}] {a['title']}"
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

    if focus_topic:
        prompt += (
            "\n\nFOCUS TOPIC (strict): "
            f"{focus_topic}\n"
            "Choose only a topic that is directly related to this focus topic. "
            "If articles include unrelated stories, ignore them. "
            f"Prioritize stories published in the last {MAX_ARTICLE_AGE_DAYS} days. "
            "Prefer themes covered by multiple trusted domains over single-source claims. "
            "Avoid hyperlocal angles unless they are clearly covered by at least 2 trusted domains. "
            "Keep the scope exact to the sources (do not over-generalize the story). "
            "Do not invent facts that are not present in the provided article list."
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
            if focus_topic:
                fallback_prompt += (
                    "\n\nFOCUS TOPIC (strict): "
                    f"{focus_topic}\n"
                    "Choose only a topic directly related to this focus topic. "
                    f"Prefer stories from the last {MAX_ARTICLE_AGE_DAYS} days. "
                    "Prefer multi-source corroboration and avoid vague unexplained labels. "
                    "Keep the scope exact to the sources (do not over-generalize the story). "
                    "Do not invent facts that are not present in the provided article list."
                )
            result = _call_openai(fallback_prompt)
        else:
            raise ValueError(f"OpenAI returned invalid JSON keys: {list(result.keys())}")

    # Normalize and clarify model output so downstream content is concrete.
    result["topic"] = _sanitize_research_text(result.get("topic", ""))
    result["topic_en"] = _sanitize_research_text(result.get("topic_en", ""))
    if "why" in result:
        result["why"] = _sanitize_research_text(result.get("why", ""))
    raw_points = result.get("key_points", [])
    if not isinstance(raw_points, list):
        raw_points = []
    result["key_points"] = [_clarify_key_point(p) for p in raw_points][:6]

    trusted_source_urls = _pick_source_urls(
        articles,
        selected_topic=result.get("topic", ""),
        focus_topic=focus_topic,
    )
    if trusted_source_urls:
        original = result.get("source_urls")
        result["source_urls"] = trusted_source_urls
        if original != trusted_source_urls:
            logger.info("Replaced model-provided source_urls with verified fetched URLs")

    # Guardrail: keep virality score in expected 1-10 range.
    raw_virality = result.get("virality_score", 7)
    try:
        virality = float(raw_virality)
    except (TypeError, ValueError):
        virality = 7.0
    virality = max(1.0, min(10.0, virality))
    # Keep integer if clean integer-like value; otherwise round to one decimal.
    result["virality_score"] = int(virality) if abs(virality - int(virality)) < 1e-9 else round(virality, 1)

    logger.info(f"Selected topic: {result['topic']} (virality: {result.get('virality_score', '?')})")
    return result


# ── Main Entry Point ────────────────────────────────────────────────────────

def _find_trending_topic_legacy(focus_topic: str | None = None) -> dict:
    """
    Main function: fetch from all sources, rank, and return the best topic.

    Returns a dict with keys: topic, topic_en, why, key_points, source_urls, virality_score
    """
    focus_topic = _normalize_focus_topic(focus_topic)
    logger.info("Starting research phase...")
    if focus_topic:
        logger.info(f"Research focus topic: {focus_topic}")
    past_topics = _get_past_topics()

    # Fetch from all sources in parallel
    all_articles = []
    trends = []

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(fetch_newsapi, focus_topic): "newsapi",
            executor.submit(fetch_rss, focus_topic): "rss",
            executor.submit(fetch_google_news_rss, focus_topic): "google_news_rss",
            executor.submit(fetch_google_news_sections, focus_topic): "google_news_sections",
            executor.submit(fetch_bing_news_rss, focus_topic): "bing_news_rss",
            executor.submit(fetch_reddit, focus_topic): "reddit",
            executor.submit(fetch_hackernews, focus_topic): "hackernews",
            executor.submit(fetch_google_trends, focus_topic): "trends",
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

    # Second pass: use Trends as query expansion to improve recall for the focus topic.
    if focus_topic and trends:
        expanded_google = fetch_google_news_rss(focus_topic, query_hints=trends[:15])
        expanded_bing = fetch_bing_news_rss(focus_topic, query_hints=trends[:15])
        all_articles.extend(expanded_google)
        all_articles.extend(expanded_bing)
        logger.info(
            "Expanded query pass added %s articles (google=%s, bing=%s)",
            len(expanded_google) + len(expanded_bing),
            len(expanded_google),
            len(expanded_bing),
        )

    all_articles = _dedupe_articles(all_articles)
    all_articles = _strict_focus_filter(all_articles, focus_topic)
    if not focus_topic:
        config = _load_research_config()
        all_articles = _filter_generic_tech_articles(
            all_articles,
            tech_keywords=list(config.get("trends_keywords", [])),
        )
    logger.info(f"Total unique articles fetched: {len(all_articles)}, trends: {len(trends)}")

    filtered_articles = _filter_recent_articles(all_articles, max_age_days=MAX_ARTICLE_AGE_DAYS)
    if filtered_articles:
        all_articles = filtered_articles
    elif all_articles:
        logger.warning(
            "No recent articles remained after recency filter; using freshest available articles"
        )
        all_articles = sorted(
            all_articles,
            key=lambda a: (_parse_published_datetime(a.get("published", "")) or datetime.min.replace(tzinfo=timezone.utc)),
            reverse=True,
        )[:MIN_RECENT_ARTICLES]

    all_articles = _filter_focus_freshness(
        all_articles,
        focus_topic=focus_topic,
        max_age_days=MAX_FOCUS_ARTICLE_AGE_DAYS,
        min_keep=MIN_FOCUS_FRESH_ARTICLES,
    )

    all_articles = _filter_low_trust_focus_articles(
        all_articles,
        focus_topic=focus_topic,
        min_trust_score=0.0,
    )

    all_articles = _prioritize_articles(
        all_articles,
        trends=trends,
        focus_topic=focus_topic,
        limit=60,
        max_per_domain=4,
    )
    _log_top_articles(all_articles, top_n=10)
    logger.info(f"Articles passed to ranking: {len(all_articles)}")

    if not all_articles and focus_topic and trends:
        logger.warning(
            "No matching articles found from news sources; falling back to Google Trends-only context."
        )
        now_iso = datetime.utcnow().isoformat() + "Z"
        all_articles = [
            {
                "title": f"{focus_topic}: {trend}",
                "description": "Trend signal from Google Trends related query.",
                "url": "",
                "source": "google_trends/related",
                "published": now_iso,
            }
            for trend in trends[:20]
        ]

    if not all_articles:
        raise RuntimeError("No articles fetched from any source. Check API keys and network.")

    # Rank and select the best topic
    topic = rank_topics(all_articles, trends, past_topics, focus_topic=focus_topic)
    return topic


def _find_trending_topic_tavily(focus_topic: str | None = None) -> dict:
    """
    Simplified research path:
    - Tavily as main source
    - Google Trends as trend signal
    - Google News RSS as resilient fallback
    """
    focus_topic = _normalize_focus_topic(focus_topic)
    logger.info("Starting research phase...")
    logger.info("Research backend: tavily")
    if focus_topic:
        logger.info(f"Research focus topic: {focus_topic}")
    past_topics = _get_past_topics()

    trends = fetch_google_trends(focus_topic)

    all_articles = fetch_tavily_news(
        focus_topic=focus_topic,
        query_hints=trends[:15] if trends else None,
    )

    fallback_articles = []
    if focus_topic:
        fallback_articles.extend(fetch_google_news_rss(focus_topic, query_hints=trends[:15] if trends else None))
        if not fallback_articles:
            fallback_articles.extend(fetch_google_news_sections(focus_topic))
    else:
        fallback_articles.extend(fetch_google_news_sections())

    if len(all_articles) < MIN_RECENT_ARTICLES and fallback_articles:
        all_articles.extend(fallback_articles)
        logger.info(
            "Google News fallback added %s articles (total before dedupe: %s)",
            len(fallback_articles),
            len(all_articles),
        )

    all_articles = _dedupe_articles(all_articles)
    all_articles = _strict_focus_filter(all_articles, focus_topic)
    if not focus_topic:
        config = _load_research_config()
        all_articles = _filter_generic_tech_articles(
            all_articles,
            tech_keywords=list(config.get("trends_keywords", [])),
        )
    logger.info(f"Total unique articles fetched: {len(all_articles)}, trends: {len(trends)}")

    filtered_articles = _filter_recent_articles(all_articles, max_age_days=MAX_ARTICLE_AGE_DAYS)
    if filtered_articles:
        all_articles = filtered_articles
    elif all_articles:
        logger.warning(
            "No recent articles remained after recency filter; using freshest available articles"
        )
        all_articles = sorted(
            all_articles,
            key=lambda a: (_parse_published_datetime(a.get("published", "")) or datetime.min.replace(tzinfo=timezone.utc)),
            reverse=True,
        )[:MIN_RECENT_ARTICLES]

    all_articles = _filter_focus_freshness(
        all_articles,
        focus_topic=focus_topic,
        max_age_days=MAX_FOCUS_ARTICLE_AGE_DAYS,
        min_keep=MIN_FOCUS_FRESH_ARTICLES,
    )

    all_articles = _filter_low_trust_focus_articles(
        all_articles,
        focus_topic=focus_topic,
        min_trust_score=0.0,
    )

    all_articles = _prioritize_articles(
        all_articles,
        trends=trends,
        focus_topic=focus_topic,
        limit=60,
        max_per_domain=4,
    )
    _log_top_articles(all_articles, top_n=10)
    logger.info(f"Articles passed to ranking: {len(all_articles)}")

    if not all_articles and focus_topic and trends:
        logger.warning(
            "No matching articles found from Tavily/RSS; falling back to Google Trends-only context."
        )
        now_iso = datetime.utcnow().isoformat() + "Z"
        all_articles = [
            {
                "title": f"{focus_topic}: {trend}",
                "description": "Trend signal from Google Trends related query.",
                "url": "",
                "source": "google_trends/related",
                "published": now_iso,
            }
            for trend in trends[:20]
        ]

    if not all_articles:
        raise RuntimeError("No articles fetched from any source. Check API keys and network.")

    topic = rank_topics(all_articles, trends, past_topics, focus_topic=focus_topic)
    return topic


def find_trending_topic(focus_topic: str | None = None) -> dict:
    """
    Main entry point with backend routing.

    Backends:
      - tavily: simplified Tavily-first research
      - legacy: original multi-source stack
      - auto: tavily when key is present, otherwise legacy
    """
    backend = _resolve_research_backend()
    if backend == "tavily":
        try:
            return _find_trending_topic_tavily(focus_topic=focus_topic)
        except Exception as e:
            logger.warning("Tavily backend failed (%s). Falling back to legacy backend.", e)
            return _find_trending_topic_legacy(focus_topic=focus_topic)
    return _find_trending_topic_legacy(focus_topic=focus_topic)


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
