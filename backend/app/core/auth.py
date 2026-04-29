from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.models.user import UserModel, utc_now


_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd_context.verify(password, password_hash)


@dataclass(slots=True)
class AuthenticatedUser:
    id: UUID
    email: str
    display_name: str
    role: str
    is_active: bool


def _encode_token(user: UserModel, settings: Settings) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=settings.auth_jwt_ttl_seconds)
    payload: dict[str, Any] = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, settings.auth_jwt_secret, algorithm="HS256")
    return token, expires_at


def _decode_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.auth_jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_token",
        ) from exc


def _decode_supabase_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_token",
        ) from exc


class UserService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def authenticate(self, email: str, password: str) -> UserModel | None:
        with self._session_factory() as session:
            user = session.scalars(
                select(UserModel).where(UserModel.email == email.lower())
            ).first()
            if user is None or not user.is_active:
                return None
            if not verify_password(password, user.password_hash):
                return None
            user.last_login_at = utc_now()
            session.commit()
            session.refresh(user)
            return user

    def get_by_id(self, user_id: UUID) -> UserModel | None:
        with self._session_factory() as session:
            return session.get(UserModel, user_id)

    def get_by_email(self, email: str) -> UserModel | None:
        with self._session_factory() as session:
            return session.scalars(
                select(UserModel).where(UserModel.email == email.lower())
            ).first()

    def create_user(
        self,
        *,
        email: str,
        password: str,
        display_name: str,
        role: str = "operator",
    ) -> UserModel:
        with self._session_factory() as session:
            user = UserModel(
                email=email.lower(),
                display_name=display_name,
                password_hash=hash_password(password),
                role=role,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            return user

    def list_users(self) -> list[UserModel]:
        with self._session_factory() as session:
            return list(session.scalars(select(UserModel).order_by(UserModel.email)).all())

    def set_password(self, user_id: UUID, new_password: str) -> bool:
        with self._session_factory() as session:
            user = session.get(UserModel, user_id)
            if user is None:
                return False
            user.password_hash = hash_password(new_password)
            session.commit()
            return True

    def set_active(self, user_id: UUID, *, active: bool) -> bool:
        with self._session_factory() as session:
            user = session.get(UserModel, user_id)
            if user is None:
                return False
            user.is_active = active
            session.commit()
            return True

    def issue_token(self, user: UserModel) -> tuple[str, datetime]:
        return _encode_token(user, get_settings())


def get_user_service(request: Request) -> UserService:
    return request.app.state.user_service


def get_current_user(
    request: Request,
    user_service: UserService = Depends(get_user_service),
) -> AuthenticatedUser:
    settings = get_settings()

    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        bearer_token = auth_header.split(" ", 1)[1].strip()
        # Supabase tokens carry audience="authenticated"; custom tokens do not.
        # Try Supabase first; fall back to custom JWT.
        try:
            payload = _decode_supabase_token(bearer_token, settings)
            email: str = payload.get("email", "")
            if not email:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")
            user = user_service.get_by_email(email)
            if user is None:
                # First Supabase login — provision a local user record.
                display_name: str = (
                    (payload.get("user_metadata") or {}).get("display_name")
                    or email.split("@")[0]
                )
                user = user_service.create_user(
                    email=email,
                    password=secrets.token_hex(32),
                    display_name=display_name,
                    role="operator",
                )
            if not user.is_active:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
            return AuthenticatedUser(
                id=user.id,
                email=user.email,
                display_name=user.display_name,
                role=user.role,
                is_active=user.is_active,
            )
        except HTTPException:
            raise
        except Exception:
            # Not a Supabase token — try legacy custom JWT below.
            pass

        try:
            payload = _decode_token(bearer_token, settings)
            user_id = UUID(payload["sub"])
        except (KeyError, ValueError, HTTPException) as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token") from exc
        user = user_service.get_by_id(user_id)
        if user is None or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
        return AuthenticatedUser(
            id=user.id, email=user.email, display_name=user.display_name,
            role=user.role, is_active=user.is_active,
        )

    # Cookie fallback (legacy / server-side requests)
    cookie_token = request.cookies.get(settings.auth_cookie_name)
    if not cookie_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
    payload = _decode_token(cookie_token, settings)
    try:
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token") from exc
    user = user_service.get_by_id(user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
    return AuthenticatedUser(
        id=user.id, email=user.email, display_name=user.display_name,
        role=user.role, is_active=user.is_active,
    )
