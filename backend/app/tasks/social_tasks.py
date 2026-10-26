"""Real social-post publishing to a connected Facebook Page (FR-CUST-05)."""
import mimetypes
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.integrations.meta_graph import (
    publish_feed_post,
    publish_multi_photo_post,
    publish_photo_post,
    upload_unpublished_photo,
)
from app.models.integration import Integration, IntegrationStatus
from app.models.social_post import SocialPost, SocialPostStatus
from app.services.media_resolver import resolve_photo_bytes as _resolve_photo_bytes


def _simple_error_message(raw: str) -> str:
    """Translate raw Meta/HTTP errors into something a shop owner can act on."""
    low = raw.lower()
    if "pages_manage_posts" in low or "permission" in low or "(#200)" in low:
        return "Facebook didn't allow this post. Please reconnect your Facebook Page under Integrations and try again."
    if "url should represent a valid url" in low or "(#100)" in low:
        return "The photo couldn't be sent to Facebook. Please remove the image, re-attach it, and try publishing again."
    if "oauth" in low or "token" in low or "access_token" in low:
        return "Your Facebook connection has expired. Please reconnect your Facebook Page under Integrations."
    if "not connected" in low or "missing token" in low:
        return "This Facebook Page isn't connected yet. Please connect it under Integrations first."
    return "Couldn't publish this post to Facebook. Please try again, or reconnect your Facebook Page under Integrations."


@celery_app.task(bind=True, max_retries=2)
def publish_social_post_task(self, post_id: str) -> dict:
    db = SessionLocal()
    try:
        post = db.get(SocialPost, uuid.UUID(post_id))
        if post is None:
            return {"error": "post not found"}

        integrations = (
            db.query(Integration)
            .filter(
                Integration.shop_id == post.shop_id,
                Integration.provider == "facebook",
                Integration.status == IntegrationStatus.CONNECTED,
            )
            .all()
        )

        resolved_page_id = None
        resolved_token = None
        resolved_page_name = None

        for integ in integrations:
            cfg = integ.config or {}
            if cfg.get("page_id"):
                pid = str(cfg["page_id"])
                pname = cfg.get("page_name") or "Facebook Page"
                ptoken = cfg.get("page_access_token")
                if not post.page_id or pid == str(post.page_id):
                    resolved_page_id = pid
                    resolved_token = ptoken
                    resolved_page_name = pname
                    break

            for p in cfg.get("pages") or []:
                pid = str(p.get("id"))
                if pid:
                    pname = p.get("name") or "Facebook Page"
                    ptoken = p.get("access_token") or cfg.get("page_access_token")
                    if not post.page_id or pid == str(post.page_id):
                        resolved_page_id = pid
                        resolved_token = ptoken
                        resolved_page_name = pname
                        break
            if resolved_page_id:
                break

        if resolved_page_name and not post.page_name:
            post.page_name = resolved_page_name
        if resolved_page_id and not post.page_id:
            post.page_id = resolved_page_id

        channel = (post.channel or "facebook").lower()
        if channel != "facebook":
            post.status = SocialPostStatus.FAILED
            post.error_message = (
                f"Live publishing to {channel} is not wired yet. "
                "Create multi-channel drafts here; publish to Facebook works today."
            )
            db.add(post)
            db.commit()
            return {"error": post.error_message}

        if not (resolved_page_id and resolved_token):
            post.status = SocialPostStatus.FAILED
            post.error_message = "Target Facebook Page not connected or missing token."
            db.add(post)
            db.commit()
            return {"error": post.error_message}

        try:
            photo_refs = [p for p in (post.photo_urls or []) if p]
            result_id = ""
            if photo_refs:
                resolved_photos: list[tuple[bytes, str]] = []
                for photo_ref in photo_refs:
                    resolved = _resolve_photo_bytes(photo_ref)
                    if resolved is None:
                        raise RuntimeError(
                            "Could not read an attached photo to publish it. "
                            "Please remove and re-attach the image(s), then retry."
                        )
                    resolved_photos.append(resolved)

                if len(resolved_photos) == 1:
                    photo_bytes, filename = resolved_photos[0]
                    content_type = mimetypes.guess_type(filename)[0] or "image/jpeg"
                    result_id = publish_photo_post(
                        str(resolved_page_id),
                        str(resolved_token),
                        post.caption or "",
                        photo_bytes=photo_bytes,
                        filename=filename,
                        content_type=content_type,
                    )
                else:
                    photo_ids = []
                    for photo_bytes, filename in resolved_photos:
                        content_type = mimetypes.guess_type(filename)[0] or "image/jpeg"
                        photo_ids.append(
                            upload_unpublished_photo(
                                str(resolved_page_id),
                                str(resolved_token),
                                photo_bytes=photo_bytes,
                                filename=filename,
                                content_type=content_type,
                            )
                        )
                    result_id = publish_multi_photo_post(
                        str(resolved_page_id), str(resolved_token), post.caption or "", photo_ids
                    )
            else:
                result_id = publish_feed_post(str(resolved_page_id), str(resolved_token), post.caption or "")
            post.status = SocialPostStatus.PUBLISHED
            post.published_at = datetime.now(timezone.utc)
            post.error_message = None

            # FR-CAT: if this post is actually selling something, add/update the matching
            # catalog product — a post that isn't about a product must never create one.
            try:
                from app.services.page_study_service import sync_products_from_published_post

                post_link = None
                if result_id and "_" in result_id:
                    pid, _, sid = result_id.partition("_")
                    post_link = f"https://www.facebook.com/{pid}/posts/{sid}"
                sync_products_from_published_post(
                    db,
                    post.shop_id,
                    post.page_id,
                    post.caption or "",
                    photo_url=photo_refs[0] if photo_refs else None,
                    post_link=post_link,
                )
            except Exception:
                # Catalog sync is a bonus on top of a successful publish — never let it
                # mark an otherwise-successful post as failed.
                pass
        except Exception as exc:
            post.status = SocialPostStatus.FAILED
            post.error_message = _simple_error_message(str(exc))

        db.add(post)
        db.commit()
        return {"status": post.status.value}
    finally:
        db.close()
