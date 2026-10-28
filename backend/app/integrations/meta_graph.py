"""Real Meta Graph API calls: publishing a post, and the OAuth2 handshake
used to connect a Shop's Facebook Page/Instagram account (FR-INT-01/02,
FR-CUST-05, social post publishing).
"""
import json
from urllib.parse import urlencode

import httpx

from app.core.config import settings


class MetaNotConfiguredError(RuntimeError):
    pass


def build_authorize_url(state: str) -> str:
    """FR-INT-02: the single guided consent link the merchant clicks to
    connect their Page — this is the "simple" path (no manual App ID/Secret
    entry) because the app's own Meta App ID is used, not the merchant's."""
    if not settings.meta_configured or not settings.meta_oauth_redirect_uri:
        raise MetaNotConfiguredError("Meta app credentials / redirect URI are not configured")
    params = {
        "client_id": settings.meta_app_id,
        "redirect_uri": settings.meta_oauth_redirect_uri,
        "state": state,
    }
    if settings.meta_login_config_id:
        # Meta now requires Instagram messaging permissions (instagram_manage_messages,
        # etc.) to be requested via a named "Facebook Login for Business" Configuration
        # created in the App Dashboard (Use Cases > Instagram API with Unified Login),
        # not as plain OAuth scopes — the configuration itself defines which permissions
        # get requested, so `scope` is omitted entirely when a config_id is set.
        params["config_id"] = settings.meta_login_config_id
    else:
        # Fallback for apps that haven't set up a Login Configuration — works for
        # Facebook Page permissions, but Meta will reject instagram_manage_messages
        # here with "Invalid Scopes" until a Configuration exists (see above).
        params["scope"] = (
            "pages_show_list,pages_messaging,instagram_basic,business_management,"
            "pages_manage_posts,pages_read_engagement"
        )
    return f"https://www.facebook.com/v19.0/dialog/oauth?{urlencode(params)}"


def exchange_code_for_token(code: str) -> dict:
    """Generic OAuth2 authorization-code exchange against Meta's token endpoint.
    Returns the provider's raw token response (access_token, token_type, expires_in, ...)."""
    if not settings.meta_configured or not settings.meta_oauth_redirect_uri:
        raise MetaNotConfiguredError("Meta app credentials / redirect URI are not configured")

    response = httpx.get(
        "https://graph.facebook.com/v19.0/oauth/access_token",
        params={
            "client_id": settings.meta_app_id,
            "client_secret": settings.meta_app_secret,
            "redirect_uri": settings.meta_oauth_redirect_uri,
            "code": code,
        },
        timeout=15.0,
    )
    response.raise_for_status()
    return response.json()


def list_pages(user_access_token: str) -> list[dict]:
    """After exchanging the OAuth code, call this to get the Pages the user
    manages (each with its own page access token, needed to publish/reply),
    along with any linked Instagram Business Accounts."""
    response = httpx.get(
        f"{settings.meta_graph_base_url}/me/accounts",
        params={
            "access_token": user_access_token,
            "fields": "id,name,category,access_token,instagram_business_account{id,username,name,profile_picture_url}",
        },
        timeout=15.0,
    )
    response.raise_for_status()
    return response.json().get("data", [])
def subscribe_page_to_app(page_id: str, page_access_token: str) -> tuple[bool, str | None]:
    """Subscribes the Page to receive Messenger/Instagram Webhook notifications for
    this App. Returns (success, error_detail) — error_detail is Meta's own error
    message when the subscription call fails, so OAuth callers can log/report why."""
    try:
        response = httpx.post(
            f"{settings.meta_graph_base_url}/{page_id}/subscribed_apps",
            params={
                "access_token": page_access_token,
                "subscribed_fields": "messages,messaging_postbacks,message_reactions",
            },
            timeout=15.0,
        )
        if response.status_code == 200 and bool(response.json().get("success", False)):
            return True, None
        try:
            err = response.json().get("error", {})
            detail = f"({err.get('code')}) {err.get('message') or response.text}"
        except Exception:
            detail = response.text
        return False, detail
    except Exception as e:
        return False, str(e)


def _check_meta_response(response: httpx.Response, action_name: str) -> dict:
    if response.status_code != 200:
        try:
            err_body = response.json().get("error", {})
            err_msg = err_body.get("message") or response.text
            err_code = err_body.get("code")
            raise RuntimeError(f"Meta Graph API error ({err_code}): {err_msg}")
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            response.raise_for_status()
    return response.json()


def publish_photo_post(
    page_id: str,
    page_access_token: str,
    caption: str,
    *,
    photo_url: str | None = None,
    photo_bytes: bytes | None = None,
    filename: str = "photo.jpg",
    content_type: str = "image/jpeg",
) -> str:
    """Publish a photo to a Facebook Page.

    Prefer multipart ``source`` upload (local bytes) so Meta does not need to
    fetch a public URL (localhost/ngrok often fails with error #100).
    """
    endpoint = f"{settings.meta_graph_base_url}/{page_id}/photos"
    if photo_bytes:
        response = httpx.post(
            endpoint,
            data={"caption": caption, "access_token": page_access_token},
            files={"source": (filename, photo_bytes, content_type)},
            timeout=60.0,
        )
    elif photo_url:
        response = httpx.post(
            endpoint,
            data={"url": photo_url, "caption": caption, "access_token": page_access_token},
            timeout=30.0,
        )
    else:
        raise ValueError("photo_bytes or photo_url is required")
    data = _check_meta_response(response, "publish_photo_post")
    return data.get("post_id") or data.get("id", "")


def upload_unpublished_photo(
    page_id: str,
    page_access_token: str,
    *,
    photo_bytes: bytes,
    filename: str = "photo.jpg",
    content_type: str = "image/jpeg",
) -> str:
    """Upload a photo to the Page's library without creating a standalone post.

    Returns the photo's id, for use as one of several ``attached_media`` items
    on a single multi-photo feed post.
    """
    response = httpx.post(
        f"{settings.meta_graph_base_url}/{page_id}/photos",
        data={"published": "false", "access_token": page_access_token},
        files={"source": (filename, photo_bytes, content_type)},
        timeout=60.0,
    )
    data = _check_meta_response(response, "upload_unpublished_photo")
    return data.get("id", "")


def publish_multi_photo_post(page_id: str, page_access_token: str, caption: str, photo_ids: list[str]) -> str:
    """Publish one feed post carrying several photos (via pre-uploaded, unpublished photo ids)."""
    response = httpx.post(
        f"{settings.meta_graph_base_url}/{page_id}/feed",
        data={
            "message": caption,
            "access_token": page_access_token,
            **{
                f"attached_media[{i}]": json.dumps({"media_fbid": pid})
                for i, pid in enumerate(photo_ids)
            },
        },
        timeout=30.0,
    )
    data = _check_meta_response(response, "publish_multi_photo_post")
    return data.get("id", "")


def publish_feed_post(page_id: str, page_access_token: str, message: str) -> str:
    """Publishes a text post to a connected Facebook Page feed."""
    response = httpx.post(
        f"{settings.meta_graph_base_url}/{page_id}/feed",
        data={"message": message, "access_token": page_access_token},
        timeout=30.0,
    )
    data = _check_meta_response(response, "publish_feed_post")
    return data.get("id", "")


def send_messenger_text(page_id: str, page_access_token: str, recipient_id: str, text: str) -> str:
    """Send an outbound Messenger / Instagram DM via the Send API."""
    response = httpx.post(
        f"{settings.meta_graph_base_url}/{page_id}/messages",
        json={
            "recipient": {"id": recipient_id},
            "messaging_type": "RESPONSE",
            "message": {"text": text},
        },
        params={"access_token": page_access_token},
        timeout=20.0,
    )
    response.raise_for_status()
    return str(response.json().get("message_id") or response.json().get("id") or "")


def fetch_page_posts_with_photos(page_id: str, page_access_token: str, limit: int = 25) -> list[dict]:
    """Fetch the connected page's own actual recent posts that have a photo
    attached — raw Meta data only (no matching/guessing here), for a caller
    to pick the best match from. Captions may be in any language the page
    actually posts in (e.g. Bangla), so matching needs real language
    understanding, not done in this function.
    """
    try:
        resp = httpx.get(
            f"{settings.meta_graph_base_url}/{page_id}/posts",
            params={
                "access_token": page_access_token,
                "fields": "message,full_picture,permalink_url",
                "limit": limit,
            },
            timeout=10.0,
        )
        if resp.status_code != 200:
            return []
        posts = resp.json().get("data", [])
    except Exception:
        return []

    return [
        {
            "message": p.get("message") or "",
            "photo_url": p["full_picture"],
            "permalink_url": p.get("permalink_url"),
        }
        for p in posts
        if p.get("full_picture")
    ]


def fetch_messenger_user_name(psid: str, page_access_token: str) -> str | None:
    """Resolve a Messenger/Instagram sender's real display name from their
    page-scoped ID — the inbound webhook payload itself never includes a
    name, only the PSID, so without this a customer only ever shows up as a
    meaningless numeric ID."""
    try:
        resp = httpx.get(
            f"{settings.meta_graph_base_url}/{psid}",
            params={"fields": "first_name,last_name", "access_token": page_access_token},
            timeout=10.0,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        name = " ".join(p for p in (data.get("first_name"), data.get("last_name")) if p)
        return name or None
    except Exception:
        return None


def send_messenger_product_carousel(
    page_id: str, page_access_token: str, recipient_id: str, products: list[dict]
) -> str:
    """Send a horizontally-scrollable product card carousel (Messenger's native
    'generic template' attachment) — one card per product with its photo,
    name, price/stock as the subtitle, so a category search like "ice cream"
    shows all matching items visually in one message, the same way a proper
    storefront chat widget does, instead of a plain text list.

    Up to 10 elements per Messenger's own limit for this template type.
    """
    elements = []
    for p in products[:10]:
        element: dict = {
            "title": p["name"][:80],
            "subtitle": p["subtitle"][:80],
        }
        if p.get("photo_url"):
            element["image_url"] = p["photo_url"]
        elements.append(element)

    response = httpx.post(
        f"{settings.meta_graph_base_url}/{page_id}/messages",
        json={
            "recipient": {"id": recipient_id},
            "messaging_type": "RESPONSE",
            "message": {
                "attachment": {
                    "type": "template",
                    "payload": {"template_type": "generic", "elements": elements},
                }
            },
        },
        params={"access_token": page_access_token},
        timeout=20.0,
    )
    response.raise_for_status()
    return str(response.json().get("message_id") or response.json().get("id") or "")


def send_messenger_image(page_id: str, page_access_token: str, recipient_id: str, image_url: str) -> str:
    """Send an outbound Messenger / Instagram DM image attachment by URL — Meta
    fetches and hosts the image itself, no upload needed on our side.

    `is_reusable` is intentionally omitted (not set to True): we resolve each
    product's photo_url fresh per request rather than needing Meta's long-term
    attachment-ID caching, and repeatedly sending the same URL with
    is_reusable=True is a known source of intermittent caching-layer errors
    on Meta's side for the exact same URL that worked moments earlier.
    """
    response = httpx.post(
        f"{settings.meta_graph_base_url}/{page_id}/messages",
        json={
            "recipient": {"id": recipient_id},
            "messaging_type": "RESPONSE",
            "message": {
                "attachment": {
                    "type": "image",
                    "payload": {"url": image_url},
                }
            },
        },
        params={"access_token": page_access_token},
        timeout=20.0,
    )
    data = _check_meta_response(response, "send_messenger_image")
    return str(data.get("message_id") or data.get("id") or "")


def reply_to_comment(comment_id: str, page_access_token: str, message: str) -> str:
    """Public reply on a Facebook/Instagram comment."""
    response = httpx.post(
        f"{settings.meta_graph_base_url}/{comment_id}/comments",
        data={"message": message, "access_token": page_access_token},
        timeout=20.0,
    )
    response.raise_for_status()
    return str(response.json().get("id") or "")


def hide_comment(comment_id: str, page_access_token: str, hide: bool = True) -> None:
    response = httpx.post(
        f"{settings.meta_graph_base_url}/{comment_id}",
        data={"is_hidden": "true" if hide else "false", "access_token": page_access_token},
        timeout=15.0,
    )
    response.raise_for_status()


def list_page_catalog_items(page_id: str, page_access_token: str) -> list[dict]:
    """Pull products from a Page's Commerce catalog (FR catalogue auto-sync).

    Falls back to an empty list when the Page has no catalog or the app lacks
    catalog permissions — callers should treat that as 'nothing to sync'.
    """
    # Try owned catalogs → products, then page products edge.
    try:
        cats = httpx.get(
            f"{settings.meta_graph_base_url}/{page_id}/owned_product_catalogs",
            params={"access_token": page_access_token, "fields": "id,name", "limit": 10},
            timeout=20.0,
        )
        if cats.status_code < 400:
            for cat in cats.json().get("data") or []:
                cid = cat.get("id")
                if not cid:
                    continue
                products = httpx.get(
                    f"{settings.meta_graph_base_url}/{cid}/products",
                    params={
                        "access_token": page_access_token,
                        "fields": "id,name,price,description,image_url,url,retailer_id",
                        "limit": 100,
                    },
                    timeout=30.0,
                )
                if products.status_code < 400:
                    data = products.json().get("data") or []
                    if data:
                        return data
    except Exception:
        pass

    for path in (f"{page_id}/products", f"{page_id}/product_catalogs"):
        try:
            response = httpx.get(
                f"{settings.meta_graph_base_url}/{path}",
                params={
                    "access_token": page_access_token,
                    "fields": "id,name,price,description,image_url,url",
                    "limit": 100,
                },
                timeout=30.0,
            )
            if response.status_code >= 400:
                continue
            data = response.json().get("data", [])
            if data:
                return data
        except Exception:
            continue
    return []


def normalize_catalog_item(item: dict) -> dict:
    """Map a Graph catalog item into our ProductCreate-ish dict."""
    price_raw = item.get("price") or item.get("price_amount") or "0"
    if isinstance(price_raw, dict):
        price_raw = price_raw.get("amount") or price_raw.get("price") or "0"
    try:
        # Meta often returns "BDT10.00" or minor units
        digits = "".join(ch if ch.isdigit() or ch == "." else "" for ch in str(price_raw))
        price = float(digits or 0)
    except ValueError:
        price = 0.0
    return {
        "external_id": str(item.get("id") or ""),
        "name": item.get("name") or "Untitled",
        "price": price,
        "description": item.get("description"),
        "photo_url": item.get("image_url") or item.get("image") or None,
    }


def fetch_messenger_user_name(psid: str, page_access_token: str) -> str | None:
    """Fetch the real display name of a Messenger user from the Graph API.

    Uses the Page-Scoped User ID (PSID) which is what Meta sends in webhook
    `sender.id`. Returns None on any error so callers can fall back gracefully.
    Requires the page access token (not a user token).
    """
    if not psid or not page_access_token:
        return None
    try:
        resp = httpx.get(
            f"{settings.meta_graph_base_url}/{psid}",
            params={
                "access_token": page_access_token,
                "fields": "name,first_name,last_name",
            },
            timeout=8.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            name = data.get("name") or (
                f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
            )
            return name or None
    except Exception:
        pass
    return None
