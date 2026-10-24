from sqlalchemy import Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Shop(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "shops"

    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="BDT")
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Dhaka")
    plan_tier: Mapped[str] = mapped_column(String(30), default="free")

    # FR-SET-03: shop profile / delivery & hours
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    opening_hours: Mapped[dict] = mapped_column(JSONB, default=dict)  # {"mon": "10:00-20:00", ...}
    delivery_charge_inside_city: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    delivery_charge_outside_city: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)

    # FR-CHAT-05: comment moderation toggles
    auto_hide_spam_comments: Mapped[bool] = mapped_column(default=True)
    auto_hide_phone_numbers_in_comments: Mapped[bool] = mapped_column(default=True)
    ai_auto_reply_comments: Mapped[bool] = mapped_column(default=False)

    # AI Control Room module switches (conversations, studio, fulfilment, money, …)
    ai_module_toggles: Mapped[dict] = mapped_column(JSONB, default=dict)

    team_members: Mapped[list["TeamMember"]] = relationship(back_populates="shop")
    products: Mapped[list["Product"]] = relationship(back_populates="shop")
    customers: Mapped[list["Customer"]] = relationship(back_populates="shop")
    orders: Mapped[list["Order"]] = relationship(back_populates="shop")
