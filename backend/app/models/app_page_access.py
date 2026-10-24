import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class AppPageVisibility(UUIDMixin, TimestampMixin, Base):
    """System Admin control over our OWN application pages/modules (Setup,
    Integrations, Products, ...) — distinct from social media Page visibility
    (see PageAIProfile.is_visible / PageUserPermission).

    - is_restricted = False (default): every team member can see this module.
    - is_restricted = True: only users with an AppPageUserPermission row for
      this page_key can see it (Super Admin always sees everything).
    """

    __tablename__ = "app_page_visibility"

    page_key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    is_restricted: Mapped[bool] = mapped_column(Boolean, default=False)


class AppPageUserPermission(UUIDMixin, TimestampMixin, Base):
    """Explicit per-user access grant for a restricted internal app page."""

    __tablename__ = "app_page_user_permissions"
    __table_args__ = (
        UniqueConstraint("page_key", "user_id", name="uq_app_page_user_permission"),
    )

    page_key: Mapped[str] = mapped_column(String(80), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("team_members.id"), index=True)
