"""
Publisher module: uploads carousel images and publishes to Instagram.

Uses the Instagram Graph API (official Meta API) for carousel publishing.

Flow:
  1. Upload each image to a public URL (Imgur or custom hosting)
  2. Create carousel container items via Graph API
  3. Create the carousel container
  4. Publish the carousel
"""

import json
import logging
import random
import time
from pathlib import Path
from urllib.parse import quote

import requests

from config.settings import (
    GRAPH_API_VERSION,
    HISTORY_FILE,
    IMGUR_CLIENT_ID,
    INSTAGRAM_ACCOUNT_ID,
    META_ACCESS_TOKEN,
    PUBLIC_IMAGE_BASE_URL,
)

logger = logging.getLogger(__name__)


def _normalize_graph_version(raw: str) -> str:
    v = (raw or "v25.0").strip()
    if not v.startswith("v"):
        v = f"v{v}"
    return v


GRAPH_API_BASE = f"https://graph.facebook.com/{_normalize_graph_version(GRAPH_API_VERSION)}"


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


def _build_public_image_url_candidates(image_path: Path) -> list[str]:
    """
    Build candidate public URLs for an image from PUBLIC_IMAGE_BASE_URL.

    It tries common layouts:
      - {base}/slide_00.png
      - {base}/slides/slide_00.png
      - {base}/output/slide_00.png
    """
    if not PUBLIC_IMAGE_BASE_URL:
        raise ValueError("PUBLIC_IMAGE_BASE_URL is not configured")

    base = PUBLIC_IMAGE_BASE_URL.rstrip("/")
    filename = quote(image_path.name)

    candidates = [
        f"{base}/{filename}",
        f"{base}/slides/{filename}",
        f"{base}/output/{filename}",
    ]

    deduped = []
    seen = set()
    for url in candidates:
        if url not in seen:
            seen.add(url)
            deduped.append(url)
    return deduped


def _check_public_image_url(image_url: str) -> tuple[bool, str]:
    """Check whether image_url is a direct, publicly fetchable image."""
    last_error = "unknown"
    for method in ("HEAD", "GET"):
        try:
            resp = requests.request(
                method,
                image_url,
                allow_redirects=True,
                timeout=20,
                stream=(method == "GET"),
            )
        except requests.RequestException as exc:
            last_error = str(exc)
            continue

        content_type = (resp.headers.get("Content-Type", "").split(";")[0].strip().lower())
        ok_status = 200 <= resp.status_code < 300
        is_image = content_type.startswith("image/")
        resp.close()

        if ok_status and is_image:
            return True, ""

        last_error = f"status={resp.status_code}, content_type={content_type or 'missing'}"

    return False, last_error


def _validate_public_image_url(image_url: str):
    """
    Validate that Meta can fetch the image URL.

    Rules:
      - HTTP 2xx
      - Content-Type starts with image/
    """
    is_ok, last_error = _check_public_image_url(image_url)
    if is_ok:
        return

    raise RuntimeError(
        f"Image URL is not valid for Instagram Graph API: {image_url} ({last_error}). "
        "Use a direct public URL that returns HTTP 200 and image/jpeg or image/png."
    )


def upload_images(image_paths: list[Path]) -> list[str]:
    """Resolve all carousel images to public URLs and validate each URL."""
    urls = []

    # Option A: direct public URLs from your own CDN/ngrok host.
    if PUBLIC_IMAGE_BASE_URL:
        logger.info("Using PUBLIC_IMAGE_BASE_URL for image hosting")
        for path in image_paths:
            candidate_urls = _build_public_image_url_candidates(path)
            resolved = None
            attempts = []
            for candidate in candidate_urls:
                is_ok, err = _check_public_image_url(candidate)
                attempts.append((candidate, err))
                if is_ok:
                    resolved = candidate
                    break

            if not resolved:
                detail = "; ".join(f"{u} ({e})" for u, e in attempts)
                raise RuntimeError(
                    f"Image URL is not valid for Instagram Graph API for {path.name}. "
                    f"Tried: {detail}. Use a direct public URL that returns HTTP 200 and image/jpeg or image/png."
                )

            urls.append(resolved)
            logger.info(f"Using public URL for {path.name} → {resolved}")
        logger.info(f"Resolved {len(urls)} images via PUBLIC_IMAGE_BASE_URL")
        return urls

    # Option B: upload to Imgur as fallback.
    if not IMGUR_CLIENT_ID:
        raise ValueError(
            "No image hosting configured. Set PUBLIC_IMAGE_BASE_URL (recommended) "
            "or IMGUR_CLIENT_ID."
        )

    for path in image_paths:
        url = _upload_to_imgur(path)
        _validate_public_image_url(url)
        urls.append(url)
        time.sleep(1)  # Rate limit respect
    logger.info(f"Uploaded {len(urls)} images via Imgur")
    return urls


# ── Instagram Graph API ─────────────────────────────────────────────────────

def _meta_error_text(resp: requests.Response) -> str:
    """Extract a human-readable Meta Graph API error."""
    try:
        payload = resp.json()
    except ValueError:
        body = (resp.text or "").strip()
        return f"HTTP {resp.status_code}: {body[:300]}"

    err = payload.get("error") if isinstance(payload, dict) else None
    if not err:
        return f"HTTP {resp.status_code}: {payload}"

    message = err.get("message", "Unknown Meta error")
    code = err.get("code")
    subcode = err.get("error_subcode")
    fbtrace = err.get("fbtrace_id")
    parts = [f"HTTP {resp.status_code}", message]
    if code is not None:
        parts.append(f"code={code}")
    if subcode is not None:
        parts.append(f"subcode={subcode}")
    if fbtrace:
        parts.append(f"fbtrace_id={fbtrace}")
    return " | ".join(parts)


def _is_meta_transient_error(resp: requests.Response) -> bool:
    """
    Decide if a Meta Graph error is likely transient and should be retried.
    """
    if resp.status_code >= 500:
        return True

    try:
        payload = resp.json()
    except ValueError:
        return False

    err = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(err, dict):
        return False

    if bool(err.get("is_transient")):
        return True

    code = err.get("code")
    # Common transient/rate/infra classes seen in Graph API
    retryable_codes = {1, 2, 4, 17, 32, 613}
    return code in retryable_codes


def _retry_sleep(attempt: int, *, base: float = 1.0, cap: float = 12.0):
    # Exponential backoff with small jitter to avoid burst retries.
    delay = min(cap, base * (2 ** max(0, attempt - 1)))
    delay += random.uniform(0.0, 0.4)
    time.sleep(delay)


def _graph_post(
    path: str,
    data: dict,
    *,
    timeout: int = 30,
    retries: int = 4,
) -> dict:
    """
    POST to Graph API with retries on transient Meta/HTTP/network failures.
    """
    url = f"{GRAPH_API_BASE}/{path.lstrip('/')}"
    attempts = max(1, retries + 1)

    for attempt in range(1, attempts + 1):
        try:
            resp = requests.post(url, data=data, timeout=timeout)
        except requests.RequestException as exc:
            if attempt >= attempts:
                raise RuntimeError(f"Meta POST {path} network failure: {exc}") from exc
            logger.warning(
                "Meta POST %s network error (attempt %d/%d): %s. Reintentando...",
                path,
                attempt,
                attempts,
                exc,
            )
            _retry_sleep(attempt)
            continue

        if resp.ok:
            return resp.json()

        err_text = _meta_error_text(resp)
        if attempt < attempts and _is_meta_transient_error(resp):
            logger.warning(
                "Meta POST %s error transitorio (attempt %d/%d): %s. Reintentando...",
                path,
                attempt,
                attempts,
                err_text,
            )
            _retry_sleep(attempt)
            continue

        raise RuntimeError(f"Meta POST {path} failed: {err_text}")

    raise RuntimeError(f"Meta POST {path} failed after retries")


def _graph_get(
    path: str,
    params: dict,
    *,
    timeout: int = 30,
    retries: int = 3,
) -> dict:
    """
    GET to Graph API with retries on transient Meta/HTTP/network failures.
    """
    url = f"{GRAPH_API_BASE}/{path.lstrip('/')}"
    attempts = max(1, retries + 1)

    for attempt in range(1, attempts + 1):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
        except requests.RequestException as exc:
            if attempt >= attempts:
                raise RuntimeError(f"Meta GET {path} network failure: {exc}") from exc
            logger.warning(
                "Meta GET %s network error (attempt %d/%d): %s. Reintentando...",
                path,
                attempt,
                attempts,
                exc,
            )
            _retry_sleep(attempt)
            continue

        if resp.ok:
            return resp.json()

        err_text = _meta_error_text(resp)
        if attempt < attempts and _is_meta_transient_error(resp):
            logger.warning(
                "Meta GET %s error transitorio (attempt %d/%d): %s. Reintentando...",
                path,
                attempt,
                attempts,
                err_text,
            )
            _retry_sleep(attempt)
            continue

        raise RuntimeError(f"Meta GET {path} failed: {err_text}")

    raise RuntimeError(f"Meta GET {path} failed after retries")


def _create_carousel_item(image_url: str) -> str:
    """Create a single carousel item container. Returns the container ID."""
    payload = _graph_post(
        f"{INSTAGRAM_ACCOUNT_ID}/media",
        data={
            "image_url": image_url,
            "is_carousel_item": "true",
            "access_token": META_ACCESS_TOKEN,
        },
    )
    container_id = payload["id"]
    logger.debug(f"Created carousel item: {container_id}")
    return container_id


def _create_carousel_container(item_ids: list[str], caption: str) -> str:
    """Create the carousel container with all items. Returns the container ID."""
    payload = _graph_post(
        f"{INSTAGRAM_ACCOUNT_ID}/media",
        data={
            "media_type": "CAROUSEL",
            "children": ",".join(item_ids),
            "caption": caption,
            "access_token": META_ACCESS_TOKEN,
        },
    )
    container_id = payload["id"]
    logger.info(f"Created carousel container: {container_id}")
    return container_id


def _publish_container(container_id: str) -> str:
    """Publish a media container. Returns the published media ID."""
    # Wait for container to be ready
    for attempt in range(12):
        status_payload = _graph_get(
            container_id,
            params={"fields": "status_code,status", "access_token": META_ACCESS_TOKEN},
            timeout=15,
        )
        status = status_payload.get("status_code")
        if status == "FINISHED":
            break
        if status in {"ERROR", "EXPIRED"}:
            raise RuntimeError(f"Container {container_id} failed with status={status}")
        logger.info(f"Container status: {status}, waiting... (attempt {attempt + 1})")
        time.sleep(5)

    payload = _graph_post(
        f"{INSTAGRAM_ACCOUNT_ID}/media_publish",
        data={"creation_id": container_id, "access_token": META_ACCESS_TOKEN},
    )
    media_id = payload["id"]
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
    if not image_paths:
        raise ValueError("No images to publish. image_paths is empty.")

    logger.info(
        "Instagram publish setup: graph=%s, image_host=%s",
        GRAPH_API_BASE,
        "PUBLIC_IMAGE_BASE_URL" if PUBLIC_IMAGE_BASE_URL else "IMGUR",
    )

    full_caption = strategy.get("full_caption", content.get("caption", ""))

    # Step 1: Upload images to public hosting
    logger.info("Step 1/3: Resolving public image URLs...")
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
    print("  1. META_ACCESS_TOKEN — for Instagram Graph API")
    print("  2. INSTAGRAM_ACCOUNT_ID — your IG business account ID")
    print("  3. PUBLIC_IMAGE_BASE_URL (recommended) OR IMGUR_CLIENT_ID")
    print("\nSet these in .env and run with real images to test.")
    print("\nTo test image upload only:")
    print("  python -c \"from modules.publisher import upload_images; ...\"")
