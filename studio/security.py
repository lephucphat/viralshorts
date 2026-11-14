"""Password hashing, signed session tokens and signed media URLs.

Passwords use scrypt (memory-hard, in the standard library). Session tokens are
HS256 JWTs built by hand: three base64url parts and an HMAC, verified in
constant time, with an expiry and a per-user ``token_version`` so a password
change revokes every older token.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from . import db

_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1
TOKEN_TTL_SECONDS = int(os.environ.get("STUDIO_TOKEN_TTL_SECONDS", str(30 * 24 * 3600)))

MIN_PASSWORD = 8
MAX_PASSWORD = 128

_secret_cache = {}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt,
                            n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32)
    return "scrypt${}${}${}${}${}".format(
        _SCRYPT_N, _SCRYPT_R, _SCRYPT_P,
        base64.b64encode(salt).decode(), base64.b64encode(digest).decode())


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, digest_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        digest = hashlib.scrypt(password.encode("utf-8"), salt=salt,
                                n=int(n), r=int(r), p=int(p), dklen=len(expected))
        return hmac.compare_digest(digest, expected)
    except Exception:
        return False


# A real hash to compare against when the email is unknown, so a login for a
# missing account costs the same as one for an existing account.
DUMMY_HASH = hash_password("not-a-real-password")


MIN_SECRET_LENGTH = 32


def production() -> bool:
    """True on a real deployment (``APP_ENV=production``; docker-compose.prod.yml sets it)."""
    return os.environ.get("APP_ENV", "").strip().lower() in ("production", "prod")


def check_production_config() -> None:
    """Refuse to start a production server that signs sessions with a guessable key.

    Without ``STUDIO_SECRET`` the module invents one and stores it beside the database,
    which is right for a laptop but means a restored backup or a second instance would sign
    differently. In production the operator must set it, long and random
    (``openssl rand -hex 32``). Does nothing outside production."""
    if not production():
        return
    value = os.environ.get("STUDIO_SECRET", "").strip()
    weak = {"changeme", "change-me", "secret", "test-secret", "dev-secret", "password"}
    if len(value) < MIN_SECRET_LENGTH or value.lower() in weak:
        raise RuntimeError(
            f"STUDIO_SECRET must be set to a random value of at least {MIN_SECRET_LENGTH} characters "
            "when APP_ENV=production (generate one with: openssl rand -hex 32).")


def _secret() -> bytes:
    """The signing key: STUDIO_SECRET, else a random key persisted beside the DB."""
    env = os.environ.get("STUDIO_SECRET")
    if env:
        return env.encode("utf-8")
    path = os.path.join(db.data_dir(), ".studio_secret")
    cached = _secret_cache.get(path)
    if cached:
        return cached
    if os.path.exists(path):
        with open(path, "rb") as fh:
            value = fh.read().strip()
    else:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        value = secrets.token_hex(32).encode()
        # Exclusive create + owner-only mode: two workers racing at first boot
        # must end up with the same key, and nobody else may read it.
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as fh:
                fh.write(value)
        except FileExistsError:
            with open(path, "rb") as fh:
                value = fh.read().strip()
    _secret_cache[path] = value
    return value


def signing_secret() -> str:
    """The secret other modules (media URL signing in app.py) key their HMACs on."""
    return _secret().decode("utf-8")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def create_token(user_id: int, token_version: int, ttl: int = None) -> str:
    now = int(time.time())
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64(json.dumps({
        "sub": str(user_id), "tv": int(token_version),
        "iat": now, "exp": now + int(ttl if ttl is not None else TOKEN_TTL_SECONDS),
    }, separators=(",", ":")).encode())
    sig = _b64(hmac.new(_secret(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


def verify_token(token: str):
    """The payload dict for a valid, unexpired token; None otherwise."""
    try:
        header, payload, sig = token.split(".")
        expected = _b64(hmac.new(_secret(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        head = json.loads(_unb64(header))
        if head.get("alg") != "HS256":
            return None
        data = json.loads(_unb64(payload))
        if int(data.get("exp", 0)) < time.time():
            return None
        return data
    except Exception:
        return None


def sign_resource(kind: str, resource_id, expires: int) -> str:
    """Short signature for a URL an <img>/<video> tag must fetch without headers."""
    msg = f"{kind}:{resource_id}:{expires}".encode()
    return hmac.new(_secret(), msg, hashlib.sha256).hexdigest()[:32]


def check_resource(kind: str, resource_id, expires: int, signature: str) -> bool:
    if not signature or int(expires or 0) < time.time():
        return False
    return hmac.compare_digest(signature, sign_resource(kind, resource_id, int(expires)))
