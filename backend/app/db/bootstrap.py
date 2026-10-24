"""Create all tables from SQLAlchemy metadata (dev bootstrap when no alembic revision yet)."""
from sqlalchemy import text

from app.db.base import Base
from app.db.session import engine
import app.models  # noqa: F401 — register models on metadata

# Lightweight additive patches for existing DBs (create_all does not ALTER).
_COLUMN_PATCHES = [
    ("messages", "delivery_status", "VARCHAR(40)"),
    ("messages", "delivery_detail", "VARCHAR(250)"),
    ("customers", "phone", "VARCHAR(80)"),
    ("ai_knowledge_items", "embedding", "JSONB"),
    ("ai_knowledge_items", "page_id", "VARCHAR(120)"),
    ("products", "embedding", "JSONB"),
    ("page_ai_profiles", "is_visible", "BOOLEAN DEFAULT TRUE"),
    ("plans", "extra_credit_rate_per_k", "NUMERIC(12, 2) DEFAULT 10.0"),
    ("plans", "extra_voice_rate_per_min", "NUMERIC(12, 2) DEFAULT 0.20"),
    ("plans", "is_active", "BOOLEAN DEFAULT TRUE"),
    ("conversations", "page_id", "VARCHAR(120)"),
    ("ai_credit_ledger_entries", "page_id", "VARCHAR(120)"),
    ("products", "page_id", "VARCHAR(120)"),
    ("orders", "conversation_id", "UUID"),
    ("orders", "customer_phone", "VARCHAR(50)"),
    ("orders", "delivery_address", "VARCHAR(500)"),
]


def _dialect_name() -> str:
    return engine.dialect.name


def _add_column_if_missing(conn, table: str, column: str, col_type: str) -> None:
    dialect = _dialect_name()
    if dialect == "sqlite":
        if col_type == "JSONB":
            col_type = "JSON"
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        existing = {r[1] for r in rows}
        if column not in existing:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
        return
    # PostgreSQL
    exists = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    ).fetchone()
    if not exists:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))


def ensure_schema() -> None:
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        for table, column, col_type in _COLUMN_PATCHES:
            try:
                _add_column_if_missing(conn, table, column, col_type)
            except Exception:
                # Table may not exist yet on first boot before create_all settled
                pass
