import hmac
import secrets
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
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
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["authentication"])
DUMMY_PASSWORD_HASH = hash_password("not-a-real-user-password")
REFRESH_COOKIE = "flowraga_refresh"
CSRF_COOKIE = "flowraga_csrf"


def normalize_email(email: str) -> str:
    return email.strip().lower()


def set_session_cookies(
    response: Response,
    refresh_token: str,
    csrf_token: str,
    settings: Settings,
) -> None:
    max_age = settings.refresh_token_days * 24 * 60 * 60
    common = {
        "secure": settings.auth_cookie_secure,
        "samesite": settings.auth_cookie_samesite,
        "domain": settings.auth_cookie_domain,
        "path": "/",
        "max_age": max_age,
    }
    response.set_cookie(REFRESH_COOKIE, refresh_token, httponly=True, **common)
    response.set_cookie(CSRF_COOKIE, csrf_token, httponly=False, **common)


def clear_session_cookies(response: Response, settings: Settings) -> None:
    for name in (REFRESH_COOKIE, CSRF_COOKIE):
        response.delete_cookie(
            name,
            domain=settings.auth_cookie_domain,
            path="/",
            secure=settings.auth_cookie_secure,
            samesite=settings.auth_cookie_samesite,
        )


def require_csrf(request: Request, header_token: str | None) -> str:
    cookie_token = request.cookies.get(CSRF_COOKIE)
    if (
        cookie_token is None
        or header_token is None
        or not hmac.compare_digest(cookie_token, header_token)
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")
    return cookie_token


async def issue_tokens(
    user: User,
    db: DbSession,
    settings: Settings,
    response: Response,
) -> tuple[TokenResponse, RefreshSession]:
    access_token, expires_in = create_access_token(user.id, settings)
    refresh = create_refresh_token(settings)
    refresh_session = RefreshSession(
        user_id=user.id,
        token_hash=refresh.digest,
        expires_at=refresh.expires_at,
    )
    db.add(refresh_session)
    await db.flush()
    csrf_token = secrets.token_urlsafe(32)
    set_session_cookies(response, refresh.raw, csrf_token, settings)
    return (
        TokenResponse(
            access_token=access_token,
            expires_in=expires_in,
            csrf_token=csrf_token,
            user=UserResponse.model_validate(user),
        ),
        refresh_session,
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    db: DbSession,
    response: Response,
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
    token_response, _ = await issue_tokens(user, db, settings, response)
    return token_response


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: DbSession,
    response: Response,
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
    token_response, _ = await issue_tokens(user, db, settings, response)
    return token_response


@router.get("/csrf")
async def csrf(response: Response, settings: Annotated[Settings, Depends(get_settings)]) -> dict:
    token = secrets.token_urlsafe(32)
    response.set_cookie(
        CSRF_COOKIE,
        token,
        httponly=False,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        domain=settings.auth_cookie_domain,
        path="/",
        max_age=10 * 60,
    )
    return {"csrf_token": token}


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: DbSession,
    settings: Annotated[Settings, Depends(get_settings)],
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> TokenResponse:
    require_csrf(request, x_csrf_token)
    raw_refresh = request.cookies.get(REFRESH_COOKIE)
    if raw_refresh is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    token_hash = hash_refresh_token(raw_refresh)
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
    token_response, replacement = await issue_tokens(user, db, settings, response)
    session.replaced_by_id = replacement.id
    return token_response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: DbSession,
    settings: Annotated[Settings, Depends(get_settings)],
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> None:
    require_csrf(request, x_csrf_token)
    raw_refresh = request.cookies.get(REFRESH_COOKIE)
    session = await db.scalar(
        select(RefreshSession).where(
            RefreshSession.token_hash == hash_refresh_token(raw_refresh or "")
        )
    )
    if session is not None and session.revoked_at is None:
        session.revoked_at = datetime.now(UTC)
    clear_session_cookies(response, settings)


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser) -> User:
    return user
