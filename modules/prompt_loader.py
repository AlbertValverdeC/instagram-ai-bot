"""
Prompt loader: reads custom prompts from data/prompts/ or returns defaults.
"""

import logging

from config.settings import PROMPTS_DIR

logger = logging.getLogger(__name__)


def load_prompt(prompt_id: str, default: str) -> str:
    """Load a custom prompt from disk, or return the hardcoded default."""
    filepath = PROMPTS_DIR / f"{prompt_id}.txt"
    if filepath.exists():
        logger.info(f"Loading custom prompt: {prompt_id}")
        return filepath.read_text(encoding="utf-8")
    return default
