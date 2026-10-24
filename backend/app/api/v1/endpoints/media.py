import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

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
