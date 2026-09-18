import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from flowraga.core.config import Settings

password_hash = PasswordHash.recommended()


class InvalidAccessTokenError(Exception):
    pass


@dataclass(frozen=True)
class RefreshToken:
    raw: str
    digest: str
    expires_at: datetime


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    return password_hash.verify(password, encoded_hash)


def create_access_token(user_id: uuid.UUID, settings: Settings) -> tuple[str, int]:
    now = datetime.now(UTC)
    expires_delta = timedelta(minutes=settings.access_token_minutes)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "nbf": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, int(expires_delta.total_seconds())


def decode_access_token(token: str, settings: Settings) -> uuid.UUID:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "type", "iss", "aud", "iat", "nbf", "exp", "jti"]},
        )
        if payload["type"] != "access":
            raise InvalidAccessTokenError
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise InvalidAccessTokenError from exc


def create_refresh_token(settings: Settings) -> RefreshToken:
    raw = secrets.token_urlsafe(48)
    return RefreshToken(
        raw=raw,
        digest=hash_refresh_token(raw),
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
    )


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
