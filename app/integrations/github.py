import hashlib
import hmac


def compute_signature(payload: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def verify_signature(payload: bytes, secret: str, signature: str | None) -> bool:
    if not signature or not signature.startswith("sha256="):
        return False
    expected = compute_signature(payload, secret)
    return hmac.compare_digest(expected, signature)
