#!/usr/bin/env python3
"""
Main pipeline: orchestrates the full Instagram AI Bot workflow.

Usage:
    python main_pipeline.py              # Full run (research → publish)
    python main_pipeline.py --dry-run    # Everything except publishing
    python main_pipeline.py --test       # Use sample data, no API calls
    python main_pipeline.py --step research     # Run only research
    python main_pipeline.py --step content      # Run only content gen (needs topic)
    python main_pipeline.py --step design       # Run only design (needs content)
    python main_pipeline.py --template 0        # Force a specific template (0-3)
"""

import argparse
import json
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import DATA_DIR, HISTORY_FILE, LOGS_DIR, OUTPUT_DIR

logger = logging.getLogger("pipeline")


def setup_logging(verbose: bool = False):
    """Configure logging to both console and file."""
    level = logging.DEBUG if verbose else logging.INFO
    log_file = LOGS_DIR / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    from config.settings import LOG_DATE_FORMAT, LOG_FORMAT

    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file),
        ],
    )
    logger.info(f"Log file: {log_file}")


def cleanup_output():
    """Remove generated slide images from output directory."""
    count = 0
    for f in OUTPUT_DIR.glob("slide_*.png"):
        f.unlink()
        count += 1
    if count:
        logger.info(f"Cleaned up {count} slide images from output/")


def get_sample_topic() -> dict:
    """Return a sample topic for --test mode."""
    return {
        "topic": "OpenAI lanza GPT-5 con razonamiento avanzado",
        "topic_en": "OpenAI launches GPT-5 with advanced reasoning",
        "why": "Major AI model release — high virality potential",
        "key_points": [
            "GPT-5 supera a GPT-4 en un 40% en benchmarks de razonamiento",
            "Nuevo modo de 'pensamiento profundo' para problemas complejos",
            "Disponible en ChatGPT Plus y API desde el primer día",
            "Capacidad multimodal mejorada: texto, imagen, audio y video",
            "Precio de API reducido un 50% respecto a GPT-4",
            "OpenAI afirma que es un paso significativo hacia AGI",
        ],
        "source_urls": ["https://example.com"],
        "virality_score": 9,
    }


def get_sample_content() -> dict:
    """Return sample content for --test mode."""
    return {
        "slides": [
            {
                "type": "cover",
                "title": "🤖 OpenAI acaba de lanzar GPT-5",
                "subtitle": "Todo lo que necesitas saber en 60 segundos",
            },
            {
                "type": "content",
                "number": 1,
                "title": "40% más inteligente",
                "body": "GPT-5 supera a GPT-4 en un 40% en benchmarks de razonamiento lógico y matemático.",
            },
            {
                "type": "content",
                "number": 2,
                "title": "Pensamiento profundo 🧠",
                "body": "Nuevo modo de razonamiento que descompone problemas complejos paso a paso antes de responder.",
            },
            {
                "type": "content",
                "number": 3,
                "title": "Multimodal total",
                "body": "Procesa texto, imagen, audio y video en una sola conversación sin cambiar de modelo.",
            },
            {
                "type": "content",
                "number": 4,
                "title": "50% más barato 💰",
                "body": "El precio de la API se reduce a la mitad, democratizando el acceso para desarrolladores.",
            },
            {
                "type": "content",
                "number": 5,
                "title": "Disponible ya ✅",
                "body": "Accesible desde el día 1 en ChatGPT Plus y a través de la API para desarrolladores.",
            },
            {
                "type": "content",
                "number": 6,
                "title": "¿Un paso hacia AGI? 🌐",
                "body": "Sam Altman afirma que GPT-5 representa un avance significativo hacia la inteligencia artificial general.",
            },
            {
                "type": "cta",
                "title": "¿Te ha sido útil? 🔖",
                "body": "Guarda este post, compártelo y sígueme para más contenido sobre IA y tecnología cada día.",
            },
        ],
        "caption": "🤖 OpenAI acaba de lanzar GPT-5 y estas son las 6 claves que necesitas saber. El mundo de la IA no para de avanzar.",
        "alt_text": "Carrusel informativo sobre el lanzamiento de GPT-5 por OpenAI con 6 puntos clave.",
        "hashtag_suggestions": ["#gpt5", "#openai2025", "#chatgpt5", "#iaavanzada", "#techactualidad"],
    }


def daily_pipeline(dry_run: bool = False, test_mode: bool = False, step: str | None = None, template_idx: int | None = None):
    """
    Execute the full daily pipeline.

    Args:
        dry_run: if True, do everything except publish
        test_mode: if True, use sample data (no API calls)
        step: if set, run only this step ('research', 'content', 'design')
        template_idx: force a specific carousel template
    """
    logger.info("=" * 60)
    logger.info(f"INSTAGRAM AI BOT — Pipeline Start")
    logger.info(f"  Mode: {'TEST' if test_mode else 'DRY-RUN' if dry_run else 'LIVE'}")
    logger.info(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if step:
        logger.info(f"  Step: {step}")
    logger.info("=" * 60)

    topic = None
    content = None
    image_paths = None
    strategy = None

    # ── Step 1: Research ─────────────────────────────────────────────────
    if step is None or step == "research":
        logger.info("\n📡 STEP 1: Research — Finding trending topic...")
        if test_mode:
            topic = get_sample_topic()
            logger.info(f"[TEST] Using sample topic: {topic['topic']}")
        else:
            from modules.researcher import find_trending_topic
            topic = find_trending_topic()

        logger.info(f"✓ Topic: {topic['topic']}")
        logger.info(f"  Virality: {topic.get('virality_score', 'N/A')}/10")
        for i, point in enumerate(topic["key_points"], 1):
            logger.info(f"  {i}. {point}")

        if step == "research":
            # Save topic for later use
            topic_file = DATA_DIR / "last_topic.json"
            with open(topic_file, "w") as f:
                json.dump(topic, f, ensure_ascii=False, indent=2)
            logger.info(f"Topic saved to {topic_file}")
            return

    # Load topic from file if running a later step
    if topic is None:
        topic_file = DATA_DIR / "last_topic.json"
        if topic_file.exists():
            with open(topic_file) as f:
                topic = json.load(f)
            logger.info(f"Loaded topic from file: {topic['topic']}")
        else:
            topic = get_sample_topic()
            logger.warning("No topic found, using sample data")

    # ── Step 2: Content Generation ───────────────────────────────────────
    if step is None or step == "content":
        logger.info("\n✍️  STEP 2: Content — Generating carousel text...")
        if test_mode:
            content = get_sample_content()
            logger.info(f"[TEST] Using sample content: {len(content['slides'])} slides")
        else:
            from modules.content_generator import generate
            content = generate(topic)

        logger.info(f"✓ Generated {len(content['slides'])} slides")
        for slide in content["slides"]:
            logger.info(f"  [{slide['type'].upper()}] {slide.get('title', '?')}")

        if step == "content":
            content_file = DATA_DIR / "last_content.json"
            with open(content_file, "w") as f:
                json.dump(content, f, ensure_ascii=False, indent=2)
            logger.info(f"Content saved to {content_file}")
            return

    # Load content from file if running a later step
    if content is None:
        content_file = DATA_DIR / "last_content.json"
        if content_file.exists():
            with open(content_file) as f:
                content = json.load(f)
            logger.info(f"Loaded content from file")
        else:
            content = get_sample_content()
            logger.warning("No content found, using sample data")

    # ── Step 3: Carousel Design ──────────────────────────────────────────
    if step is None or step == "design":
        logger.info("\n🎨 STEP 3: Design — Creating carousel images...")
        from modules.carousel_designer import create
        image_paths = create(content, template_index=template_idx, topic=topic)
        logger.info(f"✓ Created {len(image_paths)} slide images")
        for p in image_paths:
            logger.info(f"  → {p}")

        if step == "design":
            return

    # ── Step 4: Engagement Strategy ──────────────────────────────────────
    logger.info("\n📊 STEP 4: Engagement — Building strategy...")
    from modules.engagement import get_strategy
    strategy = get_strategy(topic, content)
    logger.info(f"✓ Day type: {strategy['day_type']}")
    logger.info(f"  Posting time: {strategy['posting_time']} ({strategy['timezone']})")
    logger.info(f"  Hashtags: {len(strategy['hashtags'].split())} tags")

    # ── Step 5: Publish ──────────────────────────────────────────────────
    if dry_run or test_mode:
        logger.info("\n🚫 STEP 5: Publish — SKIPPED (dry-run/test mode)")
        logger.info("  To publish for real, run without --dry-run or --test")

        # Show what would be published
        logger.info(f"\n--- PREVIEW ---")
        logger.info(f"Images: {len(image_paths or [])} slides")
        logger.info(f"Caption preview:\n{strategy['full_caption'][:500]}")
    else:
        logger.info("\n🚀 STEP 5: Publish — Uploading to Instagram...")
        from modules.publisher import publish, save_to_history

        media_id = publish(image_paths, content, strategy)
        logger.info(f"✓ Published! Media ID: {media_id}")

        # Save to history
        save_to_history(media_id, topic)
        logger.info("✓ Saved to history")

    # ── Cleanup ──────────────────────────────────────────────────────────
    if not dry_run and not test_mode:
        cleanup_output()

    logger.info("\n" + "=" * 60)
    logger.info("Pipeline complete!")
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Instagram AI Bot — Daily Content Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main_pipeline.py                    # Full live run
  python main_pipeline.py --dry-run          # Everything except publishing
  python main_pipeline.py --test             # Sample data, no APIs
  python main_pipeline.py --step research    # Only find trending topic
  python main_pipeline.py --step design      # Only generate images
  python main_pipeline.py --template 2       # Use template #2 (dark_green)
        """,
    )
    parser.add_argument("--dry-run", action="store_true", help="Run without publishing")
    parser.add_argument("--test", action="store_true", help="Use sample data (no API calls)")
    parser.add_argument("--step", choices=["research", "content", "design"], help="Run a single step")
    parser.add_argument("--template", type=int, choices=[0, 1, 2, 3], help="Force template index")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    try:
        daily_pipeline(
            dry_run=args.dry_run,
            test_mode=args.test,
            step=args.step,
            template_idx=args.template,
        )
    except KeyboardInterrupt:
        logger.info("\nPipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\nPipeline failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
