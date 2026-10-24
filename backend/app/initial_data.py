"""Seed a demo Shop + Super Admin + catalogues for local development.

Usage: python -m app.initial_data
"""
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.integration import DialectPack, Integration, IntegrationCategory, IntegrationStatus
from app.models.plan import Plan, PlanCode, ShopSubscription
from app.models.shop import Shop
from app.models.team_member import TeamMember, TeamRole

DEMO_EMAIL = "owner@demo-shop.test"
DEMO_PASSWORD = "ChangeMe123!"

DIALECT_SEEDS = [
    ("bn-STD", "Standard Bangla", "ga", 0.12),
    ("bn-SYL", "Sylheti", "beta", 0.28),
    ("bn-CTG", "Chittagonian", "beta", 0.30),
    ("bn-RAJ", "Rajshahi / North Bengal", "beta", 0.25),
    ("bn-KHU", "Khulna / South-West", "beta", 0.27),
    ("bn-BAR", "Barisal", "beta", 0.29),
    ("bn-MYM", "Mymensingh", "beta", 0.26),
    ("en", "English", "ga", 0.08),
    ("hi", "Hindi", "ga", 0.10),
    ("ur", "Urdu", "beta", 0.22),
]

INTEGRATION_SEEDS = [
    ("facebook", IntegrationCategory.MESSAGING),
    ("instagram", IntegrationCategory.MESSAGING),
    ("whatsapp", IntegrationCategory.MESSAGING),
    ("twilio", IntegrationCategory.TELEPHONY),
    ("bkash", IntegrationCategory.PAYMENT),
    ("nagad", IntegrationCategory.PAYMENT),
    ("stripe", IntegrationCategory.PAYMENT),
    ("sslcommerz", IntegrationCategory.PAYMENT),
    ("pathao", IntegrationCategory.COURIER),
    ("steadfast", IntegrationCategory.COURIER),
    ("google", IntegrationCategory.PRODUCTIVITY),
    ("smtp", IntegrationCategory.EMAIL),
    ("telegram", IntegrationCategory.MESSAGING),
    ("tiktok", IntegrationCategory.MESSAGING),
]


PLAN_SEEDS = [
    (PlanCode.FREE, "Free", 0, 1, 2, 60, 0),
    (PlanCode.PRO, "Pro", 1990, 3, 5, 500, 60),
    (PlanCode.BUSINESS, "Business", 4990, 6, 15, 2000, 300),
    (PlanCode.ENTERPRISE, "Enterprise", 0, 99, 99, 10000, 2000),
]


def _seed_plans(db) -> None:
    for code, name, price, channels, seats, credits, voice in PLAN_SEEDS:
        if db.query(Plan).filter(Plan.code == code).first():
            continue
        db.add(
            Plan(
                code=code,
                name=name,
                monthly_price=price,
                channel_limit=channels,
                team_seat_limit=seats,
                monthly_ai_credits=credits,
                monthly_voice_minutes=voice,
            )
        )


def _seed_dialects(db) -> None:
    for code, label, accuracy, wer in DIALECT_SEEDS:
        exists = db.query(DialectPack).filter(DialectPack.language_code == code).first()
        if exists:
            continue
        db.add(
            DialectPack(
                language_code=code,
                region_label=label,
                accuracy_status=accuracy,
                word_error_rate=wer,
            )
        )


def _ensure_subscription(db, shop_id) -> None:
    if db.query(ShopSubscription).filter(ShopSubscription.shop_id == shop_id).first():
        return
    db.add(ShopSubscription(shop_id=shop_id, plan_code=PlanCode.FREE, status="active"))


def _seed_integrations(db, shop_id) -> None:
    for provider, category in INTEGRATION_SEEDS:
        exists = (
            db.query(Integration)
            .filter(Integration.shop_id == shop_id, Integration.provider == provider)
            .first()
        )
        if exists:
            continue
        db.add(
            Integration(
                shop_id=shop_id,
                provider=provider,
                category=category,
                status=IntegrationStatus.NOT_CONNECTED,
                config={},
            )
        )


def run() -> None:
    from app.db.bootstrap import ensure_schema

    print("Ensuring database schema…")
    ensure_schema()

    db = SessionLocal()
    try:
        _seed_dialects(db)
        _seed_plans(db)

        existing = db.query(TeamMember).filter(TeamMember.email == DEMO_EMAIL).first()
        if existing:
            _seed_integrations(db, existing.shop_id)
            _ensure_subscription(db, existing.shop_id)
            db.commit()
            print(f"Demo user already exists: {DEMO_EMAIL} (catalogues refreshed)")
            return

        shop = Shop(name="Demo Shop", category="general_retail", plan_tier="free")
        db.add(shop)
        db.flush()

        owner = TeamMember(
            shop_id=shop.id,
            email=DEMO_EMAIL,
            hashed_password=hash_password(DEMO_PASSWORD),
            first_name="Demo",
            last_name="Owner",
            role=TeamRole.SUPER_ADMIN,
        )
        db.add(owner)
        _seed_integrations(db, shop.id)
        _ensure_subscription(db, shop.id)
        db.commit()
        print(f"Created demo shop '{shop.name}' and user {DEMO_EMAIL} / {DEMO_PASSWORD}")
        print("Seeded dialect packs + integration catalogue.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
