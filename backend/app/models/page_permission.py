import uuid
from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class PageUserPermission(UUIDMixin, TimestampMixin, Base):
    """User-specific page permissions configured by System Admin (Product Owner).

    Guarantees:
    - If a page is marked invisible: no regular user can see it.
    - If a page is marked visible: only users with an explicit permission row can see it.
    - System Admin (Super Admin) is the Product Owner and has master visibility over all pages.
    """

    __tablename__ = "page_user_permissions"
    __table_args__ = (
        UniqueConstraint("page_id", "user_id", name="uq_page_user_permission"),
    )

    shop_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shops.id"), index=True)
    page_id: Mapped[str] = mapped_column(String(120), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("team_members.id"), index=True)

    can_view: Mapped[bool] = mapped_column(Boolean, default=True)
    can_manage: Mapped[bool] = mapped_column(Boolean, default=False)
