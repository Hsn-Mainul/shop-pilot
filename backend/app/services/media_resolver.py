"""Resolve a stored media reference (local upload path or served URL) to raw bytes.

Shared by anything that needs the actual file content rather than a URL —
e.g. publishing a photo to Meta (which can't fetch a localhost URL), or
running an uploaded image through a vision model for AI caption generation.
"""
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.api.v1.endpoints.media import STORAGE_ROOT
from app.core.config import settings


def absolute_url(url: str) -> str:
    if url.startswith("http://") or url.startswith("https://"):
        return url
    base = settings.public_base_url.rstrip("/")
    return f"{base}{url if url.startswith('/') else '/' + url}"


def local_media_file(url_or_path: str) -> Path | None:
    """Map a media API path/URL back to the on-disk upload file."""
    marker = "/api/v1/media/files/"
    raw = url_or_path
    if marker not in raw:
        parsed = urlparse(url_or_path)
        raw = parsed.path or url_or_path
    if marker not in raw:
        return None
    rest = raw.split(marker, 1)[1]
    parts = [p for p in rest.split("/") if p]
    if len(parts) < 2:
        return None
    shop_id, filename = parts[0], Path(parts[1]).name
    path = STORAGE_ROOT / shop_id / filename
    return path if path.is_file() else None


def resolve_photo_bytes(photo_ref: str) -> tuple[bytes, str] | None:
    """Resolve a stored photo reference to raw bytes, preferring the on-disk
    file and falling back to an HTTP fetch of its served URL."""
    local = local_media_file(photo_ref)
    if local is not None:
        return local.read_bytes(), local.name

    url = absolute_url(photo_ref)
    try:
        resp = httpx.get(url, timeout=30.0)
        resp.raise_for_status()
        filename = Path(urlparse(url).path).name or "photo.jpg"
        return resp.content, filename
    except Exception:
        return None
