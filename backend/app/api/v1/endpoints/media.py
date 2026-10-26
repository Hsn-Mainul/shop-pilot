import uuid
from pathlib import Path
from urllib.parse import unquote

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse

from app.api.deps import require_role
from app.core.config import settings
from app.models.team_member import TeamMember, TeamRole

router = APIRouter(prefix="/media", tags=["media"])

STORAGE_ROOT = Path(__file__).resolve().parents[3] / "storage" / "uploads"
ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf", ".txt", ".csv", ".mp3", ".wav", ".ogg", ".webm"}


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_media(
    file: UploadFile = File(...),
    current_user: TeamMember = Depends(require_role(TeamRole.SALES)),
) -> dict:
    """Store an uploaded file and return an absolute URL Meta/browser can fetch."""
    original = file.filename or "upload.bin"
    ext = Path(original).suffix.lower()
    if ext and ext not in ALLOWED_EXT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '{ext}' not allowed",
        )

    shop_dir = STORAGE_ROOT / str(current_user.shop_id)
    shop_dir.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4()
    safe_name = f"{file_id}{ext or ''}"
    dest = shop_dir / safe_name

    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File too large (max 15MB)")
    dest.write_bytes(data)

    path = f"/api/v1/media/files/{current_user.shop_id}/{safe_name}"
    base = settings.public_base_url.rstrip("/")
    return {
        "url": f"{base}{path}",
        "path": path,
        "filename": original,
        "content_type": file.content_type,
        "size": len(data),
    }


@router.get("/files/{shop_id}/{filename}")
def get_media_file(shop_id: uuid.UUID, filename: str) -> FileResponse:
    """Public file fetch (needed for <img> preview and Meta Graph photo URL)."""
    safe = Path(filename).name
    path = STORAGE_ROOT / str(shop_id) / safe
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return FileResponse(path)


@router.get("/proxy")
def proxy_external_image(
    url: str = Query(..., description="External image URL to proxy"),
    token: str | None = Query(None, description="Bearer token for auth"),
) -> StreamingResponse:
    """Proxy an external image (e.g. Facebook CDN) through the backend so the
    browser can display it without hitting CORS / Referer restrictions.

    Auth: pass ?token=<jwt> (used because <img> tags cannot send Authorization headers).
    Only http/https URLs are accepted; localhost/private ranges are blocked.
    """
    # Validate token — reuse the same JWT logic as the regular auth dependency
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    from app.core.security import decode_token
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    decoded = unquote(url)

    # Only allow http/https — block file:// / data: / javascript: etc.
    if not decoded.startswith(("http://", "https://")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only http/https URLs are allowed")

    # Block requests to private / loopback addresses (SSRF guard)
    from urllib.parse import urlparse
    try:
        hostname = urlparse(decoded).hostname or ""
        if hostname in ("localhost", "127.0.0.1", "::1") or hostname.startswith("192.168.") or hostname.startswith("10."):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Private addresses are not allowed")
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid URL")

    try:
        resp = httpx.get(
            decoded,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; ChatbotProxy/1.0)",
                "Referer": "https://www.facebook.com/",
                # When `decoded` is our own ngrok-tunneled upload URL (used so Facebook/Meta
                # can fetch it), ngrok's free tier serves an HTML interstitial warning page
                # instead of the real file unless this header is present — harmless to send
                # for any other host, like the Facebook CDN URLs this proxy also handles.
                "ngrok-skip-browser-warning": "true",
            },
            timeout=15.0,
            follow_redirects=True,
        )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Could not fetch image: {exc}")

    if resp.status_code != 200:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Remote returned {resp.status_code}")

    content_type = resp.headers.get("content-type", "image/jpeg")
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="URL does not point to an image")

    return StreamingResponse(
        iter([resp.content]),
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )
