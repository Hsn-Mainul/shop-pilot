import enum
import uuid

from sqlalchemy import Date, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class LeaveStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Shift(UUIDMixin, TimestampMixin, Base):
    """AI-drafted or confirmed shift plan for a team member on a given day (FR-TEAM-04)."""

    __tablename__ = "shifts"

    shop_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shops.id"), index=True)
    team_member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("team_members.id"), index=True)
    shift_date: Mapped[Date] = mapped_column(Date)
    planned_hours: Mapped[int] = mapped_column(Integer, default=8)
    is_confirmed: Mapped[bool] = mapped_column(default=False)


class LeaveRequest(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "leave_requests"

    team_member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("team_members.id"), index=True)
    start_date: Mapped[Date] = mapped_column(Date)
    end_date: Mapped[Date] = mapped_column(Date)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[LeaveStatus] = mapped_column(Enum(LeaveStatus), default=LeaveStatus.PENDING)


class DataHygieneIssueType(str, enum.Enum):
    DUPLICATE_CUSTOMER = "duplicate_customer"
    NON_STANDARD_PHONE = "non_standard_phone"
    MISSING_PRICE = "missing_price"
    MISSING_PHOTO = "missing_photo"


class DataHygieneIssue(UUIDMixin, TimestampMixin, Base):
    """Dismissible data-quality finding (FR-TEAM-05)."""

    __tablename__ = "data_hygiene_issues"

    shop_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shops.id"), index=True)
    issue_type: Mapped[DataHygieneIssueType] = mapped_column(Enum(DataHygieneIssueType))
    related_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))  # customer_id or product_id depending on type
    is_resolved: Mapped[bool] = mapped_column(default=False)
