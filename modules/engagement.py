"""
Engagement strategy module: hashtags, timing, caption assembly.

Combines:
  - Hashtag pools (high/medium/niche competition)
  - Context-specific hashtags from content generator
  - Caption structure with CTA
  - Optimal posting time calculation
"""

import logging
import random
from datetime import datetime

from config.engagement import (
    CAPTION_STRUCTURE,
    CTA_PHRASES,
    CTA_QUESTIONS,
    DEFAULT_SLOT,
    HASHTAGS_DISTRIBUTION,
    HASHTAGS_HIGH_COMPETITION,
    HASHTAGS_MEDIUM_COMPETITION,
    HASHTAGS_NICHE,
    POSTING_HOURS,
)
from config.settings import TIMEZONE

logger = logging.getLogger(__name__)


def _select_hashtags(contextual_hashtags: list[str] | None = None) -> str:
    """
    Select a mix of hashtags from different pools.
    Returns a string of space-separated hashtags (max 30).
    """
    selected = []

    # Pick from each pool
    high = random.sample(
        HASHTAGS_HIGH_COMPETITION,
        min(HASHTAGS_DISTRIBUTION["high"], len(HASHTAGS_HIGH_COMPETITION)),
    )
    medium = random.sample(
        HASHTAGS_MEDIUM_COMPETITION,
        min(HASHTAGS_DISTRIBUTION["medium"], len(HASHTAGS_MEDIUM_COMPETITION)),
    )
    niche = random.sample(
        HASHTAGS_NICHE,
        min(HASHTAGS_DISTRIBUTION["niche"], len(HASHTAGS_NICHE)),
    )

    selected = high + medium + niche

    # Add contextual hashtags (replace some niche ones to stay at 30)
    if contextual_hashtags:
        for tag in contextual_hashtags:
            tag = tag if tag.startswith("#") else f"#{tag}"
            if tag not in selected and len(selected) < 30:
                selected.append(tag)

    # Ensure max 30
    selected = selected[:30]
    random.shuffle(selected)

    return " ".join(selected)


def _get_cta() -> tuple[str, str]:
    """Get a random CTA phrase and question."""
    phrase = random.choice(CTA_PHRASES)
    question = random.choice(CTA_QUESTIONS)
    return phrase, question


def _build_caption(content: dict, hashtags_str: str) -> str:
    """Assemble the full Instagram caption."""
    caption = content.get("caption", "")
    _, cta_question = _get_cta()

    full_caption = CAPTION_STRUCTURE.format(
        hook=caption,
        summary="",  # The caption from OpenAI already includes context
        cta_question=cta_question,
        hashtags=hashtags_str,
    ).strip()

    # Clean up multiple blank lines
    while "\n\n\n" in full_caption:
        full_caption = full_caption.replace("\n\n\n", "\n\n")

    return full_caption


def get_optimal_time() -> str:
    """Get the optimal posting time for today."""
    today = datetime.now()
    weekday = today.weekday()  # 0=Monday, 6=Sunday

    if weekday == 6:  # Sunday
        return POSTING_HOURS.get("sunday") or POSTING_HOURS[DEFAULT_SLOT]
    elif weekday == 5:  # Saturday
        return POSTING_HOURS.get("saturday", POSTING_HOURS[DEFAULT_SLOT])
    else:
        return POSTING_HOURS[DEFAULT_SLOT]


def get_strategy(topic: dict, content: dict) -> dict:
    """
    Build the full engagement strategy for a post.

    Args:
        topic: dict from researcher
        content: dict from content_generator

    Returns:
        dict with keys: hashtags, full_caption, posting_time, day_type
    """
    today = datetime.now()
    weekday = today.weekday()

    # Determine day type
    if weekday == 6:
        day_type = "sunday_rest"
    elif weekday == 5:
        day_type = "saturday_recap"
    else:
        day_type = "weekday_carousel"

    # Get contextual hashtags from content generator
    contextual = content.get("hashtag_suggestions", [])

    # Build hashtags
    hashtags_str = _select_hashtags(contextual)

    # Build full caption
    full_caption = _build_caption(content, hashtags_str)

    # Get posting time
    posting_time = get_optimal_time()

    strategy = {
        "hashtags": hashtags_str,
        "full_caption": full_caption,
        "posting_time": posting_time,
        "day_type": day_type,
        "timezone": TIMEZONE,
    }

    logger.info(f"Strategy: {day_type}, post at {posting_time} {TIMEZONE}, {len(hashtags_str.split())} hashtags")
    return strategy


# ── CLI Test Mode ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    sample_topic = {"topic": "Test topic"}
    sample_content = {
        "caption": "🤖 OpenAI acaba de lanzar GPT-5 y esto es lo que necesitas saber.",
        "hashtag_suggestions": ["#gpt5", "#openai", "#chatgpt5", "#iaactualidad"],
    }

    print("=" * 60)
    print("ENGAGEMENT MODULE — Test Mode")
    print("=" * 60)

    strategy = get_strategy(sample_topic, sample_content)
    print(f"\nDay type: {strategy['day_type']}")
    print(f"Posting time: {strategy['posting_time']} ({strategy['timezone']})")
    print(f"\nHashtags ({len(strategy['hashtags'].split())}):")
    print(f"  {strategy['hashtags']}")
    print(f"\nFull caption:\n{strategy['full_caption']}")
