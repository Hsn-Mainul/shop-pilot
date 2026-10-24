"""Per-provider webhook signature verification + shop-configurable exotic schemes."""
import base64
import hashlib
import hmac
import time
from collections.abc import Callable


def verify_meta_signature(payload: bytes, header_signature: str | None, app_secret: str) -> bool:
    if not header_signature or not header_signature.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), payload, hashlib.sha256).hexdigest()
    provided = header_signature.removeprefix("sha256=")
    return hmac.compare_digest(expected, provided)


def verify_generic_hmac_signature(payload: bytes, header_signature: str | None, shared_secret: str) -> bool:
    if not header_signature:
        return False
    provided = header_signature.removeprefix("sha256=")
    expected = hmac.new(shared_secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided)


def verify_stripe_signature(payload: bytes, header_signature: str | None, webhook_secret: str) -> bool:
    if not header_signature:
        return False
    parts = dict(item.split("=", 1) for item in header_signature.split(",") if "=" in item)
    timestamp = parts.get("t")
    signature = parts.get("v1")
    if not timestamp or not signature:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs(int(time.time()) - ts) > 300:
        return False
    signed = f"{timestamp}.".encode() + payload
    expected = hmac.new(webhook_secret.encode(), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_twilio_signature(payload: bytes, header_signature: str | None, auth_token: str) -> bool:
    if not header_signature:
        return False
    expected = hmac.new(auth_token.encode(), payload, hashlib.sha256).hexdigest()
    if hmac.compare_digest(expected, header_signature):
        return True
    digest = hmac.new(auth_token.encode(), payload, hashlib.sha1).digest()
    b64 = base64.b64encode(digest).decode()
    return hmac.compare_digest(b64, header_signature)


def verify_svix_signature(payload: bytes, header_signature: str | None, secret: str) -> bool:
    if not header_signature or not secret:
        return False
    candidates = [p.split(",", 1)[1] for p in header_signature.split(" ") if "," in p]
    if not candidates:
        candidates = [header_signature]
    key = secret.removeprefix("whsec_")
    try:
        key_bytes = base64.b64decode(key)
    except Exception:
        key_bytes = key.encode()
    expected = hmac.new(key_bytes, payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, c) for c in candidates)


def verify_sha1_hmac(payload: bytes, header_signature: str | None, shared_secret: str) -> bool:
    if not header_signature:
        return False
    expected = hmac.new(shared_secret.encode(), payload, hashlib.sha1).hexdigest()
    provided = header_signature.removeprefix("sha1=")
    return hmac.compare_digest(expected, provided)


def verify_md5_body(payload: bytes, header_signature: str | None, _shared_secret: str) -> bool:
    """Some legacy gateways send MD5(body) as the signature (secret unused)."""
    if not header_signature:
        return False
    expected = hashlib.md5(payload).hexdigest()
    return hmac.compare_digest(expected, header_signature.lower())


ALGORITHM_VERIFIERS: dict[str, Callable[[bytes, str | None, str], bool]] = {
    "meta_sha256": verify_meta_signature,
    "hmac_sha256": verify_generic_hmac_signature,
    "hmac_sha1": verify_sha1_hmac,
    "stripe": verify_stripe_signature,
    "twilio": verify_twilio_signature,
    "svix": verify_svix_signature,
    "md5_body": verify_md5_body,
}


def verify_with_algo(
    algo: str,
    payload: bytes,
    header_signature: str | None,
    secret: str,
) -> bool:
    """Verify using an Integration.config['signature_algo'] value for exotic providers."""
    fn = ALGORITHM_VERIFIERS.get(algo) or ALGORITHM_VERIFIERS.get(algo.lower())
    if fn is None:
        return False
    return fn(payload, header_signature, secret)


PROVIDER_VERIFIERS = {
    "facebook": (verify_meta_signature, "X-Hub-Signature-256"),
    "instagram": (verify_meta_signature, "X-Hub-Signature-256"),
    "whatsapp": (verify_meta_signature, "X-Hub-Signature-256"),
    "bkash": (verify_generic_hmac_signature, "X-Signature"),
    "nagad": (verify_generic_hmac_signature, "X-Signature"),
    "sslcommerz": (verify_generic_hmac_signature, "X-Signature"),
    "pathao": (verify_generic_hmac_signature, "X-Signature"),
    "steadfast": (verify_generic_hmac_signature, "X-Signature"),
    "stripe": (verify_stripe_signature, "Stripe-Signature"),
    "twilio": (verify_twilio_signature, "X-Twilio-Signature"),
    "sms": (verify_twilio_signature, "X-Twilio-Signature"),
    "payment": (verify_generic_hmac_signature, "X-Signature"),
    "courier": (verify_generic_hmac_signature, "X-Signature"),
    "custom": (verify_generic_hmac_signature, "X-Signature"),
}
