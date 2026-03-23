import hmac
import hashlib
import secrets

from server.config import settings


def generate_api_key() -> str:
    return secrets.token_hex(32)


def hash_api_key(api_key: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode(),
        api_key.encode(),
        hashlib.sha256,
    ).hexdigest()


def verify_api_key(provided_key: str, stored_hash: str) -> bool:
    expected = hash_api_key(provided_key)
    return hmac.compare_digest(expected, stored_hash)
