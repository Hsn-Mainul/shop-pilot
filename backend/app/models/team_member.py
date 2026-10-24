import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class TeamRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    SALES = "sales"
    SUPPORT = "support"
    WAREHOUSE = "warehouse"


# Ordering used for "role or above" permission checks (see api/deps.py).
ROLE_RANK: dict[TeamRole, int] = {
    TeamRole.WAREHOUSE: 0,
    TeamRole.SUPPORT: 1,
    TeamRole.SALES: 1,
    TeamRole.ADMIN: 2,
    TeamRole.SUPER_ADMIN: 3,
}


class TeamMember(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "team_members"

    shop_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shops.id"))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    role: Mapped[TeamRole] = mapped_column(Enum(TeamRole), default=TeamRole.ADMIN)
    is_active: Mapped[bool] = mapped_column(default=True)
    last_active_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    shop: Mapped["Shop"] = relationship(back_populates="team_members")
