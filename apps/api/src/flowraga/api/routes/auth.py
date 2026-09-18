from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from flowraga.auth.dependencies import CurrentUser
from flowraga.auth.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from flowraga.core.config import Settings, get_settings
from flowraga.db.dependencies import DbSession
from flowraga.db.models import RefreshSession, User
from flowraga.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["authentication"])
DUMMY_PASSWORD_HASH = hash_password("not-a-real-user-password")


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def issue_tokens(user: User, db: DbSession, settings: Settings) -> TokenResponse:
    access_token, expires_in = create_access_token(user.id, settings)
    refresh = create_refresh_token(settings)
    db.add(
        RefreshSession(
            user_id=user.id,
            token_hash=refresh.digest,
            expires_at=refresh.expires_at,
        )
    )
    await db.flush()
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh.raw,
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    db: DbSession,
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    email = normalize_email(str(payload.email))
    if await db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account already exists")

    user = User(
        email=email,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Account already exists"
        ) from None
    await db.refresh(user)
    return await issue_tokens(user, db, settings)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: DbSession,
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    user = await db.scalar(select(User).where(User.email == normalize_email(str(payload.email))))
    password_valid = verify_password(
        payload.password,
        user.password_hash if user is not None else DUMMY_PASSWORD_HASH,
    )
    if user is None or not user.is_active or not password_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return await issue_tokens(user, db, settings)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    db: DbSession,
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    token_hash = hash_refresh_token(payload.refresh_token)
    session = await db.scalar(
        select(RefreshSession).where(RefreshSession.token_hash == token_hash).with_for_update()
    )
    now = datetime.now(UTC)
    session_expiry = session.expires_at if session is not None else now
    if session_expiry.tzinfo is None:
        session_expiry = session_expiry.replace(tzinfo=UTC)
    if session is None or session.revoked_at is not None or session_expiry <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    user = await db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    session.revoked_at = now
    response = await issue_tokens(user, db, settings)
    replacement = await db.scalar(
        select(RefreshSession).where(
            RefreshSession.token_hash == hash_refresh_token(response.refresh_token)
        )
    )
    session.replaced_by_id = replacement.id if replacement else None
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: LogoutRequest, db: DbSession) -> None:
    session = await db.scalar(
        select(RefreshSession).where(
            RefreshSession.token_hash == hash_refresh_token(payload.refresh_token)
        )
    )
    if session is not None and session.revoked_at is None:
        session.revoked_at = datetime.now(UTC)


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser) -> User:
    return user
