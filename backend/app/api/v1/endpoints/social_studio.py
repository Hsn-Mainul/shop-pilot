import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.session import get_db
from app.models.social_post import SocialPost, SocialPostStatus
from app.models.team_member import TeamMember, TeamRole
from app.schemas.social_post import SocialPostCreate, SocialPostOut, SocialPostUpdate
from app.tasks.social_tasks import publish_social_post_task

router = APIRouter(prefix="/social-posts", tags=["social-studio"])


@router.get("", response_model=list[SocialPostOut])
def list_social_posts(
    current_user: TeamMember = Depends(require_role(TeamRole.SALES)),
    db: Session = Depends(get_db),
) -> list[SocialPostOut]:
    return (
        db.query(SocialPost)
        .filter(SocialPost.shop_id == current_user.shop_id)
        .order_by(SocialPost.created_at.desc())
        .all()
    )


@router.post("", response_model=SocialPostOut, status_code=status.HTTP_201_CREATED)
def create_social_post(
    payload: SocialPostCreate,
    current_user: TeamMember = Depends(require_role(TeamRole.SALES)),
    db: Session = Depends(get_db),
) -> SocialPostOut:
    status_value = SocialPostStatus.SCHEDULED if payload.scheduled_at else SocialPostStatus.DRAFT
    post = SocialPost(shop_id=current_user.shop_id, status=status_value, **payload.model_dump())
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def _get_owned_post(post_id: uuid.UUID, current_user: TeamMember, db: Session) -> SocialPost:
    post = (
        db.query(SocialPost)
        .filter(SocialPost.id == post_id, SocialPost.shop_id == current_user.shop_id)
        .first()
    )
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post


@router.patch("/{post_id}", response_model=SocialPostOut)
def update_social_post(
    post_id: uuid.UUID,
    payload: SocialPostUpdate,
    current_user: TeamMember = Depends(require_role(TeamRole.SALES)),
    db: Session = Depends(get_db),
) -> SocialPostOut:
    post = _get_owned_post(post_id, current_user, db)
    if post.status == SocialPostStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This post is already published and can no longer be edited.",
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(post, field, value)

    if post.status == SocialPostStatus.FAILED:
        post.status = SocialPostStatus.SCHEDULED if post.scheduled_at else SocialPostStatus.DRAFT
        post.error_message = None

    db.add(post)
    db.commit()
    db.refresh(post)
    return post


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_social_post(
    post_id: uuid.UUID,
    current_user: TeamMember = Depends(require_role(TeamRole.SALES)),
    db: Session = Depends(get_db),
) -> None:
    post = _get_owned_post(post_id, current_user, db)
    db.delete(post)
    db.commit()


@router.post("/{post_id}/publish", response_model=SocialPostOut)
def publish_social_post(
    post_id: uuid.UUID,
    current_user: TeamMember = Depends(require_role(TeamRole.SALES)),
    db: Session = Depends(get_db),
) -> SocialPostOut:
    post = (
        db.query(SocialPost)
        .filter(SocialPost.id == post_id, SocialPost.shop_id == current_user.shop_id)
        .first()
    )
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    # FR-CUST-05: genuinely publish via the Meta Graph API (see
    # app/integrations/meta_graph.py), asynchronously through Celery so this
    # request doesn't block on an external API call. The post stays SCHEDULED
    # until the worker confirms success/failure.
    post.status = SocialPostStatus.SCHEDULED
    db.add(post)
    db.commit()
    db.refresh(post)

    try:
        publish_social_post_task.delay(str(post.id))
    except Exception:
        try:
            publish_social_post_task(str(post.id))
            db.refresh(post)
        except Exception:
            post.status = SocialPostStatus.FAILED
            db.add(post)
            db.commit()
            db.refresh(post)

    return post
