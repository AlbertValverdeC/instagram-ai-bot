"""
Publisher module: uploads carousel images and publishes to Instagram.

Uses the Instagram Graph API (official Meta API) for carousel publishing.
Falls back to instagrapi (unofficial) if configured.

Flow:
  1. Upload each image to a public URL (Imgur or custom hosting)
  2. Create carousel container items via Graph API
  3. Create the carousel container
  4. Publish the carousel
"""

import json
import logging
import time
from pathlib import Path

import requests

from config.settings import (
    HISTORY_FILE,
    IMGUR_CLIENT_ID,
    INSTAGRAM_ACCOUNT_ID,
    META_ACCESS_TOKEN,
)

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


# ── Image Hosting (Imgur) ────────────────────────────────────────────────────

def _upload_to_imgur(image_path: Path) -> str:
    """Upload an image to Imgur and return the public URL."""
    if not IMGUR_CLIENT_ID:
        raise ValueError("IMGUR_CLIENT_ID not set. Required for image hosting.")

    with open(image_path, "rb") as f:
        resp = requests.post(
            "https://api.imgur.com/3/image",
            headers={"Authorization": f"Client-ID {IMGUR_CLIENT_ID}"},
            files={"image": f},
            timeout=30,
        )
    resp.raise_for_status()
    data = resp.json()
    url = data["data"]["link"]
    logger.info(f"Uploaded {image_path.name} → {url}")
    return url


def upload_images(image_paths: list[Path]) -> list[str]:
    """Upload all carousel images and return their public URLs."""
    urls = []
    for path in image_paths:
        url = _upload_to_imgur(path)
        urls.append(url)
        time.sleep(1)  # Rate limit respect
    logger.info(f"Uploaded {len(urls)} images")
    return urls


# ── Instagram Graph API ─────────────────────────────────────────────────────

def _create_carousel_item(image_url: str) -> str:
    """Create a single carousel item container. Returns the container ID."""
    resp = requests.post(
        f"{GRAPH_API_BASE}/{INSTAGRAM_ACCOUNT_ID}/media",
        data={
            "image_url": image_url,
            "is_carousel_item": "true",
            "access_token": META_ACCESS_TOKEN,
        },
        timeout=30,
    )
    resp.raise_for_status()
    container_id = resp.json()["id"]
    logger.debug(f"Created carousel item: {container_id}")
    return container_id


def _create_carousel_container(item_ids: list[str], caption: str) -> str:
    """Create the carousel container with all items. Returns the container ID."""
    resp = requests.post(
        f"{GRAPH_API_BASE}/{INSTAGRAM_ACCOUNT_ID}/media",
        data={
            "media_type": "CAROUSEL",
            "children": ",".join(item_ids),
            "caption": caption,
            "access_token": META_ACCESS_TOKEN,
        },
        timeout=30,
    )
    resp.raise_for_status()
    container_id = resp.json()["id"]
    logger.info(f"Created carousel container: {container_id}")
    return container_id


def _publish_container(container_id: str) -> str:
    """Publish a media container. Returns the published media ID."""
    # Wait for container to be ready
    for attempt in range(10):
        status_resp = requests.get(
            f"{GRAPH_API_BASE}/{container_id}",
            params={
                "fields": "status_code",
                "access_token": META_ACCESS_TOKEN,
            },
            timeout=15,
        )
        status = status_resp.json().get("status_code")
        if status == "FINISHED":
            break
        logger.info(f"Container status: {status}, waiting... (attempt {attempt + 1})")
        time.sleep(5)

    resp = requests.post(
        f"{GRAPH_API_BASE}/{INSTAGRAM_ACCOUNT_ID}/media_publish",
        data={
            "creation_id": container_id,
            "access_token": META_ACCESS_TOKEN,
        },
        timeout=30,
    )
    resp.raise_for_status()
    media_id = resp.json()["id"]
    logger.info(f"Published! Media ID: {media_id}")
    return media_id


def publish(image_paths: list[Path], content: dict, strategy: dict) -> str:
    """
    Full publish flow: upload images → create carousel → publish.

    Args:
        image_paths: list of slide image paths
        content: dict with 'caption' key
        strategy: dict with 'full_caption' key (caption + hashtags)

    Returns:
        Instagram media ID of the published post
    """
    if not META_ACCESS_TOKEN or not INSTAGRAM_ACCOUNT_ID:
        raise ValueError(
            "META_ACCESS_TOKEN and INSTAGRAM_ACCOUNT_ID must be set. "
            "See .env.example for setup instructions."
        )

    full_caption = strategy.get("full_caption", content.get("caption", ""))

    # Step 1: Upload images to public hosting
    logger.info("Step 1/3: Uploading images...")
    image_urls = upload_images(image_paths)

    # Step 2: Create carousel items
    logger.info("Step 2/3: Creating carousel items...")
    item_ids = []
    for url in image_urls:
        item_id = _create_carousel_item(url)
        item_ids.append(item_id)
        time.sleep(1)

    # Step 3: Create and publish carousel
    logger.info("Step 3/3: Publishing carousel...")
    container_id = _create_carousel_container(item_ids, full_caption)
    media_id = _publish_container(container_id)

    return media_id


# ── History Management ───────────────────────────────────────────────────────

def save_to_history(media_id: str, topic: dict):
    """Save the published post to history.json."""
    history = []
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            history = json.load(f)

    from datetime import datetime
    entry = {
        "media_id": media_id,
        "topic": topic.get("topic", ""),
        "topic_en": topic.get("topic_en", ""),
        "published_at": datetime.now().isoformat(),
        "virality_score": topic.get("virality_score"),
    }
    history.append(entry)

    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved to history: {entry['topic']}")


# ── CLI Test Mode ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    print("=" * 60)
    print("PUBLISHER MODULE — Test Mode")
    print("=" * 60)
    print("\nThis module requires:")
    print("  1. IMGUR_CLIENT_ID — for image hosting")
    print("  2. META_ACCESS_TOKEN — for Instagram Graph API")
    print("  3. INSTAGRAM_ACCOUNT_ID — your IG business account ID")
    print("\nSet these in .env and run with real images to test.")
    print("\nTo test image upload only:")
    print("  python -c \"from modules.publisher import upload_images; ...\"")
