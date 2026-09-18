import uuid

import pytest

from flowraga.auth.security import (
    InvalidAccessTokenError,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from flowraga.core.config import Settings


def test_passwords_are_argon2_hashed() -> None:
    encoded = hash_password("correct-horse-battery-staple")
    assert encoded.startswith("$argon2")
    assert "correct-horse" not in encoded
    assert verify_password("correct-horse-battery-staple", encoded)
    assert not verify_password("wrong-password", encoded)


def test_access_token_round_trip_and_tampering_rejection() -> None:
    settings = Settings(environment="test")
    user_id = uuid.uuid4()
    token, expires_in = create_access_token(user_id, settings)

    assert expires_in == 900
    assert decode_access_token(token, settings) == user_id

    with pytest.raises(InvalidAccessTokenError):
        decode_access_token(f"{token}tampered", settings)


def test_refresh_token_stores_only_digest() -> None:
    refresh = create_refresh_token(Settings(environment="test"))
    assert len(refresh.raw) >= 64
    assert len(refresh.digest) == 64
    assert refresh.raw != refresh.digest
