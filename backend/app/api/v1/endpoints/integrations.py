import uuid
from datetime import timedelta
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.config import settings
from app.core.security import create_token, decode_token
from app.db.session import get_db
from app.integrations.meta_graph import (
    MetaNotConfiguredError,
    build_authorize_url,
    exchange_code_for_token,
    list_page_catalog_items,
    list_pages,
    normalize_catalog_item,
    subscribe_page_to_app,
)
from app.models.integration import (
    DialectPack,
    Integration,
    IntegrationCategory,
    IntegrationStatus,
    ShopDialectPreference,
)
from app.models.product import Product, ProductVariant
from app.models.team_member import TeamMember, TeamRole
from app.schemas.integration import DialectPackOut, DialectPackToggle, IntegrationConnectRequest, IntegrationOut

router = APIRouter(tags=["integrations"])

def _oauth_spec(provider: str) -> dict | None:
    """Resolve OAuth app credentials for non-Meta providers."""
    if provider == "google":
        return {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_oauth_redirect_uri
            or f"{settings.public_base_url.rstrip('/')}/api/v1/integrations/google/oauth/callback",
            "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "scope": "openid email profile https://www.googleapis.com/auth/business.manage",
        }
    if provider == "stripe":
        return {
            "client_id": settings.stripe_client_id,
            "client_secret": settings.stripe_client_secret,
            "redirect_uri": settings.stripe_oauth_redirect_uri
            or f"{settings.public_base_url.rstrip('/')}/api/v1/integrations/stripe/oauth/callback",
            "authorize_url": "https://connect.stripe.com/oauth/authorize",
            "token_url": "https://connect.stripe.com/oauth/token",
            "scope": "read_write",
        }
    return None


@router.get("/integrations", response_model=list[IntegrationOut])
def list_integrations(
    category: IntegrationCategory | None = None,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> list[IntegrationOut]:
    query = db.query(Integration).filter(Integration.shop_id == current_user.shop_id)
    if category:
        query = query.filter(Integration.category == category)
    results = query.all()

    # Filter pages for non-superadmins based on visibility mark and user-specific permissions
    if current_user.role != TeamRole.SUPER_ADMIN:
        from app.models.page_ai_profile import PageAIProfile
        from app.models.page_permission import PageUserPermission

        invisible_pids = {
            row[0]
            for row in db.query(PageAIProfile.page_id)
            .filter(PageAIProfile.shop_id == current_user.shop_id, PageAIProfile.is_visible.is_(False))
            .all()
        }
        permitted_pids = {
            row[0]
            for row in db.query(PageUserPermission.page_id)
            .filter(PageUserPermission.user_id == current_user.id, PageUserPermission.can_view.is_(True))
            .all()
        }

        for item in results:
            if item.provider in ("facebook", "instagram") and item.config and "pages" in item.config:
                filtered_pages = [
                    p for p in item.config.get("pages", [])
                    if str(p.get("id")) not in invisible_pids and str(p.get("id")) in permitted_pids
                ]
                item.config = {**item.config, "pages": filtered_pages, "connected_count": len(filtered_pages)}

    return results


@router.post("/integrations/{provider}/connect", response_model=IntegrationOut)
def connect_integration(
    provider: str,
    payload: IntegrationConnectRequest,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> IntegrationOut:
    integration = (
        db.query(Integration)
        .filter(Integration.shop_id == current_user.shop_id, Integration.provider == provider)
        .first()
    )
    if integration is None:
        integration = Integration(
            shop_id=current_user.shop_id,
            provider=provider,
            category=IntegrationCategory.MESSAGING,
            status=IntegrationStatus.NOT_CONNECTED,
            config={},
        )
        db.add(integration)
        db.flush()

    # Prefer real OAuth when this provider has app credentials configured.
    spec = _oauth_spec(provider)
    if spec and spec.get("client_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Use GET /integrations/{provider}/oauth/authorize-url for OAuth connect",
        )

    integration.status = IntegrationStatus.CONNECTED
    integration.config = {**(integration.config or {}), **payload.config}
    if payload.config.get("api_key") or payload.config.get("webhook_secret"):
        integration.credentials_ref = f"vault:{provider}:{current_user.shop_id}"
    db.add(integration)
    db.commit()
    db.refresh(integration)
    return integration


@router.get("/integrations/{provider}/oauth/authorize-url")
def get_provider_authorize_url(
    provider: str,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
) -> dict:
    """OAuth authorize URL for Google / Stripe Connect (and similar)."""
    if provider == "facebook":
        return get_facebook_authorize_url(current_user)

    spec = _oauth_spec(provider)
    if spec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No OAuth flow for this provider")
    client_id = spec.get("client_id")
    redirect_uri = spec.get("redirect_uri")
    if not client_id or not redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{provider} OAuth credentials are not configured on the server",
        )

    state = create_token(
        subject=str(current_user.shop_id),
        extra_claims={"type": "oauth_state", "provider": provider},
        expires_delta=timedelta(minutes=10),
    )
    params: dict[str, str] = {
        "client_id": str(client_id),
        "redirect_uri": str(redirect_uri),
        "response_type": "code",
        "scope": str(spec["scope"]),
        "state": state,
    }
    if provider == "google":
        params["access_type"] = "offline"
        params["prompt"] = "consent"
    return {"authorize_url": f"{spec['authorize_url']}?{urlencode(params)}", "provider": provider}


@router.get("/integrations/{provider}/oauth/callback")
def provider_oauth_callback(
    provider: str,
    code: str,
    state: str,
    db: Session = Depends(get_db),
) -> dict:
    if provider == "facebook":
        return facebook_oauth_callback(code, state, db)

    spec = _oauth_spec(provider)
    if spec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown OAuth provider")

    state_payload = decode_token(state)
    if state_payload is None or state_payload.get("type") != "oauth_state":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired state")
    shop_id = uuid.UUID(state_payload["sub"])

    response = httpx.post(
        str(spec["token_url"]),
        data={
            "client_id": spec["client_id"],
            "client_secret": spec["client_secret"],
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": spec["redirect_uri"],
        },
        timeout=20.0,
    )
    response.raise_for_status()
    token_body = response.json()

    integration = (
        db.query(Integration).filter(Integration.shop_id == shop_id, Integration.provider == provider).first()
    )
    if integration is None:
        category = IntegrationCategory.PRODUCTIVITY if provider == "google" else IntegrationCategory.PAYMENT
        integration = Integration(shop_id=shop_id, provider=provider, category=category)

    integration.status = IntegrationStatus.CONNECTED
    integration.config = {
        **(integration.config or {}),
        "access_token": token_body.get("access_token"),
        "refresh_token": token_body.get("refresh_token"),
        "stripe_user_id": token_body.get("stripe_user_id"),
        "token_type": token_body.get("token_type"),
    }
    integration.credentials_ref = f"oauth:{provider}:{shop_id}"
    db.add(integration)
    db.commit()
    return {"connected": True, "provider": provider}


@router.delete("/integrations/{provider}", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_integration(
    provider: str,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> None:
    integration = (
        db.query(Integration)
        .filter(Integration.shop_id == current_user.shop_id, Integration.provider == provider)
        .first()
    )
    if integration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    integration.status = IntegrationStatus.NOT_CONNECTED
    integration.credentials_ref = None
    integration.config = {}
    db.add(integration)
    db.commit()


@router.get("/integrations/facebook/oauth/authorize-url")
def get_facebook_authorize_url(
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
) -> dict:
    """FR-INT-02: the single guided consent link — the merchant just clicks
    this, no manual App ID/Secret entry (that's the app's own Meta App,
    configured once via settings, not per-shop)."""
    # Short-lived signed state carrying which Shop this callback is for,
    # since Meta's redirect back to us carries no auth header of its own.
    state = create_token(
        subject=str(current_user.shop_id), extra_claims={"type": "oauth_state"}, expires_delta=timedelta(minutes=10)
    )
    try:
        url = build_authorize_url(state)
    except MetaNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    return {"authorize_url": url}


@router.get("/integrations/facebook/oauth/callback")
def facebook_oauth_callback(code: str, state: str, db: Session = Depends(get_db)) -> dict:
    """Public callback Meta redirects the merchant's browser back to after
    consent. Exchanges the code for a token, lists the Pages the user manages,
    and stores the first Page's id + page access token on the Integration."""
    state_payload = decode_token(state)
    if state_payload is None or state_payload.get("type") != "oauth_state":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired state")
    shop_id = uuid.UUID(state_payload["sub"])

    try:
        token_response = exchange_code_for_token(code)
        pages = list_pages(token_response["access_token"])
    except MetaNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    if not pages:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No Facebook Pages found for this account")

    formatted_pages = [
        {
            "id": p.get("id"),
            "name": p.get("name"),
            "category": p.get("category", "Business"),
            "messenger_enabled": True,
            "comments_enabled": True,
            "access_token": p.get("access_token"),
        }
        for p in pages
    ]
    instagram_accounts = []
    for p in pages:
        ig = p.get("instagram_business_account")
        if ig and ig.get("id"):
            instagram_accounts.append({
                "id": ig.get("id"),
                "username": ig.get("username") or p.get("name"),
                "name": ig.get("name") or p.get("name"),
                "profile_picture_url": ig.get("profile_picture_url"),
                "linked_page_id": p.get("id"),
                "comments_enabled": True,
                "dm_enabled": True,
                "story_replies_enabled": False,
                "story_mentions_enabled": False,
                "page_access_token": p.get("access_token"),
            })

    page = pages[0]
    integration = (
        db.query(Integration).filter(Integration.shop_id == shop_id, Integration.provider == "facebook").first()
    )
    if integration is None:
        integration = Integration(shop_id=shop_id, provider="facebook", category=IntegrationCategory.MESSAGING)

    integration.status = IntegrationStatus.CONNECTED
    integration.config = {
        **(integration.config or {}),
        "page_id": page["id"],
        "page_access_token": page["access_token"],
        "page_name": page.get("name"),
        "pages": formatted_pages,
        "connected_count": len(formatted_pages),
    }
    db.add(integration)

    if instagram_accounts:
        ig_integration = (
            db.query(Integration).filter(Integration.shop_id == shop_id, Integration.provider == "instagram").first()
        )
        if ig_integration is None:
            ig_integration = Integration(shop_id=shop_id, provider="instagram", category=IntegrationCategory.MESSAGING)
        ig_integration.status = IntegrationStatus.CONNECTED
        ig_integration.config = {
            **(ig_integration.config or {}),
            "accounts": instagram_accounts,
            "connected_count": len(instagram_accounts),
            "account_name": instagram_accounts[0]["username"],
        }
    # Auto-subscribe each page to receive Messenger webhooks and study with AI
    from app.services.page_study_service import study_and_sync_page_profile
    for p in pages:
        pid = p.get("id")
        ptoken = p.get("access_token")
        pname = p.get("name") or "Facebook Page"
        pcat = p.get("category")
        if pid and ptoken:
            ok, err_detail = subscribe_page_to_app(pid, ptoken)
            if not ok:
                import logging

                logging.getLogger(__name__).error(
                    "subscribe_page_to_app failed for page %s (%s): %s", pid, pname, err_detail
                )
            try:
                study_and_sync_page_profile(
                    db=db,
                    shop_id=shop_id,
                    page_id=str(pid),
                    page_name=pname,
                    category=pcat,
                    page_access_token=ptoken,
                    platform="facebook",
                )
            except Exception:
                pass

    db.commit()

    frontend_url = settings.cors_origin_list[0] if settings.cors_origin_list else "http://localhost:5175"
    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Connected to Facebook</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #f8fafc; color: #1e293b; }}
    .card {{ background: white; padding: 36px 44px; border-radius: 18px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); text-align: center; max-width: 440px; border: 1px solid #e2e8f0; }}
    .icon {{ width: 64px; height: 64px; background: #1877F2; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 18px; }}
    h2 {{ font-size: 22px; margin: 0 0 10px; font-weight: 700; color: #0f172a; }}
    p {{ font-size: 15px; color: #64748b; margin: 0 0 20px; line-height: 1.5; }}
    .badge {{ display: inline-block; background: #eff6ff; color: #2563eb; padding: 6px 14px; border-radius: 20px; font-weight: 600; font-size: 13px; margin-bottom: 20px; }}
    .btn {{ display: inline-block; background: #007a5a; color: white; text-decoration: none; padding: 12px 24px; border-radius: 10px; font-weight: 600; font-size: 14px; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">
      <svg width="34" height="34" viewBox="0 0 24 24" fill="white"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>
    </div>
    <div class="badge">✓ {len(formatted_pages)} Facebook Page(s) Linked</div>
    <h2>Facebook Connected!</h2>
    <p>Your Facebook pages have been linked successfully. Returning to your ShopPilot dashboard...</p>
    <a href="{frontend_url}/integrations" class="btn">Return to Dashboard</a>
  </div>
  <script>
    if (window.opener) {{
      try {{
        window.opener.postMessage({{ type: 'oauth_connected', provider: 'facebook' }}, '*');
      }} catch (e) {{}}
      setTimeout(function() {{ window.close(); }}, 1000);
    }} else {{
      setTimeout(function() {{ window.location.href = '{frontend_url}/integrations'; }}, 1200);
    }}
  </script>
</body>
</html>"""
    return HTMLResponse(content=html_content)


@router.post("/integrations/facebook/sync-catalogue")
def sync_facebook_catalogue(
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    """FR: pull products from the connected Facebook Page catalogue into the shop."""
    integration = (
        db.query(Integration)
        .filter(
            Integration.shop_id == current_user.shop_id,
            Integration.provider == "facebook",
            Integration.status == IntegrationStatus.CONNECTED,
        )
        .first()
    )
    if integration is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Facebook Page not connected")

    page_id = (integration.config or {}).get("page_id")
    token = (integration.config or {}).get("page_access_token")
    if not page_id or not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Page credentials missing")

    raw_items = list_page_catalog_items(page_id, token)
    created = 0
    updated = 0
    for raw in raw_items:
        item = normalize_catalog_item(raw)
        if not item["name"]:
            continue
        existing = (
            db.query(Product)
            .filter(Product.shop_id == current_user.shop_id, Product.page_id == page_id, Product.name == item["name"])
            .first()
        )
        if existing:
            existing.price = item["price"] or existing.price
            if item.get("description"):
                existing.description = item["description"]
            if item.get("photo_url"):
                existing.photo_url = item["photo_url"]
            db.add(existing)
            updated += 1
        else:
            product = Product(
                shop_id=current_user.shop_id,
                page_id=page_id,
                name=item["name"],
                price=item["price"] or 0,
                description=item.get("description"),
                photo_url=item.get("photo_url"),
                kind="product",
                category="facebook_sync",
            )
            product.variants = [ProductVariant(attributes={"size": "default"}, stock_qty=0, reorder_point=2)]
            db.add(product)
            created += 1

    db.commit()
    return {"created": created, "updated": updated, "fetched": len(raw_items)}


@router.get("/dialect-packs", response_model=list[DialectPackOut])
def list_dialect_packs(db: Session = Depends(get_db)) -> list[DialectPackOut]:
    packs = db.query(DialectPack).all()
    if not packs:
        # Self-heal empty DB (same seeds as initial_data)
        for code, label, accuracy, wer in [
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
        ]:
            db.add(
                DialectPack(
                    language_code=code,
                    region_label=label,
                    accuracy_status=accuracy,
                    word_error_rate=wer,
                )
            )
        db.commit()
        packs = db.query(DialectPack).all()
    return packs


@router.patch("/dialect-packs/{pack_id}")
def toggle_dialect_pack(
    pack_id: uuid.UUID,
    payload: DialectPackToggle,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    pref = (
        db.query(ShopDialectPreference)
        .filter(
            ShopDialectPreference.shop_id == current_user.shop_id,
            ShopDialectPreference.dialect_pack_id == pack_id,
        )
        .first()
    )
    if pref is None:
        pref = ShopDialectPreference(
            shop_id=current_user.shop_id, dialect_pack_id=pack_id, is_enabled=payload.is_enabled
        )
    else:
        pref.is_enabled = payload.is_enabled
    db.add(pref)
    db.commit()
    return {"dialect_pack_id": pack_id, "is_enabled": payload.is_enabled}
