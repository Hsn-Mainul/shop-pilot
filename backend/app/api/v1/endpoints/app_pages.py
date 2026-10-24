"""Any authenticated user: which internal app pages/modules they may see.

Separate from /system-admin/app-pages (Super Admin management endpoints).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.app_page_access import AppPageUserPermission, AppPageVisibility
from app.models.team_member import TeamMember, TeamRole

router = APIRouter(tags=["app-pages"])


@router.get("/me/hidden-pages", response_model=list[str])
def get_my_hidden_pages(
    current_user: TeamMember = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[str]:
    """Internal app page keys this user may NOT see (fail-open by design: an
    empty/errored response must never hide the whole menu). Super Admin
    always sees everything."""
    if current_user.role == TeamRole.SUPER_ADMIN:
        return []

    try:
        restricted_keys = {
            c.page_key for c in db.query(AppPageVisibility).filter(AppPageVisibility.is_restricted.is_(True)).all()
        }
    except Exception:
        return []
    if not restricted_keys:
        return []

    permitted_keys = {
        p.page_key
        for p in db.query(AppPageUserPermission)
        .filter(AppPageUserPermission.user_id == current_user.id, AppPageUserPermission.page_key.in_(restricted_keys))
        .all()
    }
    return sorted(restricted_keys - permitted_keys)
