import enum
import uuid

from sqlalchemy import Enum, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class IntegrationCategory(str, enum.Enum):
    MESSAGING = "messaging"
    TELEPHONY = "telephony"
    PAYMENT = "payment"
    COURIER = "courier"
    SHOP_BUILDER = "shop_builder"
    MARKETPLACE = "marketplace"
    PRODUCTIVITY = "productivity"
    EMAIL = "email"
    AI_PROVIDER = "ai_provider"
    DEVELOPER_TOOLS = "developer_tools"


class IntegrationStatus(str, enum.Enum):
    NOT_CONNECTED = "not_connected"
    CONNECTED = "connected"
    NEEDS_ATTENTION = "needs_attention"
    PLANNED = "planned"


class Integration(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "integrations"

    shop_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shops.id"), index=True)
    provider: Mapped[str] = mapped_column(String(50))  # facebook, whatsapp, bkash, pathao, ...
    category: Mapped[IntegrationCategory] = mapped_column(Enum(IntegrationCategory))
    status: Mapped[IntegrationStatus] = mapped_column(Enum(IntegrationStatus), default=IntegrationStatus.NOT_CONNECTED)
    # Never store raw secrets here — this references an entry in a secrets manager / encrypted vault.
    credentials_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)


class DialectPack(UUIDMixin, TimestampMixin, Base):
    """Reference catalogue of supported language/dialect speech models (FR-CALL-05/06)."""

    __tablename__ = "dialect_packs"

    language_code: Mapped[str] = mapped_column(String(20), unique=True)  # bn-STD, bn-SYL, bn-CTG, en, ...
    region_label: Mapped[str] = mapped_column(String(100))
    accuracy_status: Mapped[str] = mapped_column(String(20), default="beta")  # beta, ga
    word_error_rate: Mapped[float | None] = mapped_column(Float, nullable=True)


class ShopDialectPreference(UUIDMixin, TimestampMixin, Base):
    """Which dialect packs a Shop has enabled (FR-CALL-06)."""

    __tablename__ = "shop_dialect_preferences"

    shop_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shops.id"), index=True)
    dialect_pack_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dialect_packs.id"), index=True)
    is_enabled: Mapped[bool] = mapped_column(default=True)
