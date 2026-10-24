import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.support import SupportRequest, SupportRequestStatus
from app.models.team_member import TeamMember, TeamRole
from app.schemas.support import SupportRequestCreate, SupportRequestOut

router = APIRouter(prefix="/support-requests", tags=["support"])


@router.get("", response_model=list[SupportRequestOut])
def list_support_requests(
    status_filter: SupportRequestStatus | None = None,
    current_user: TeamMember = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SupportRequestOut]:
    query = db.query(SupportRequest).filter(SupportRequest.shop_id == current_user.shop_id)
    if status_filter:
        query = query.filter(SupportRequest.status == status_filter)
    return query.order_by(SupportRequest.created_at.desc()).all()


@router.post("", response_model=SupportRequestOut, status_code=status.HTTP_201_CREATED)
def create_support_request(
    payload: SupportRequestCreate,
    current_user: TeamMember = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SupportRequestOut:
    request = SupportRequest(shop_id=current_user.shop_id, created_by=current_user.id, **payload.model_dump())
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


@router.patch("/{request_id}/close", response_model=SupportRequestOut)
def close_support_request(
    request_id: uuid.UUID,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> SupportRequestOut:
    request = (
        db.query(SupportRequest)
        .filter(SupportRequest.id == request_id, SupportRequest.shop_id == current_user.shop_id)
        .first()
    )
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support request not found")
    request.status = SupportRequestStatus.CLOSED
    db.add(request)
    db.commit()
    db.refresh(request)
    return request
