import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.saved_reply import SavedReply
from app.models.team_member import TeamMember, TeamRole
from app.schemas.saved_reply import SavedReplyCreate, SavedReplyOut, SavedReplyUpdate

router = APIRouter(prefix="/saved-replies", tags=["saved-replies"])


@router.get("", response_model=list[SavedReplyOut])
def list_saved_replies(
    current_user: TeamMember = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SavedReplyOut]:
    return (
        db.query(SavedReply)
        .filter(SavedReply.shop_id == current_user.shop_id)
        .order_by(SavedReply.usage_count.desc())
        .all()
    )


@router.post("", response_model=SavedReplyOut, status_code=status.HTTP_201_CREATED)
def create_saved_reply(
    payload: SavedReplyCreate,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> SavedReplyOut:
    reply = SavedReply(shop_id=current_user.shop_id, **payload.model_dump())
    db.add(reply)
    db.commit()
    db.refresh(reply)
    return reply


@router.patch("/{reply_id}", response_model=SavedReplyOut)
def update_saved_reply(
    reply_id: uuid.UUID,
    payload: SavedReplyUpdate,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> SavedReplyOut:
    reply = (
        db.query(SavedReply)
        .filter(SavedReply.id == reply_id, SavedReply.shop_id == current_user.shop_id)
        .first()
    )
    if reply is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved reply not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(reply, field, value)
    db.add(reply)
    db.commit()
    db.refresh(reply)
    return reply


@router.delete("/{reply_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_reply(
    reply_id: uuid.UUID,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> None:
    reply = (
        db.query(SavedReply)
        .filter(SavedReply.id == reply_id, SavedReply.shop_id == current_user.shop_id)
        .first()
    )
    if reply is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved reply not found")
    db.delete(reply)
    db.commit()
