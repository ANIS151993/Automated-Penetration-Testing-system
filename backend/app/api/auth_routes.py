from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.core.auth import (
    AuthenticatedUser,
    UserService,
    get_current_user,
    get_user_service,
)
from app.core.config import get_settings
from app.schemas.auth import LoginRequest, TokenResponse, UserCreate, UserRead, UserSetActive, UserSetPassword


auth_router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.auth_jwt_ttl_seconds,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
    )


@auth_router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    response: Response,
    user_service: UserService = Depends(get_user_service),
) -> TokenResponse:
    user = user_service.authenticate(payload.email, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_credentials",
        )
    token, expires_at = user_service.issue_token(user)
    _set_session_cookie(response, token)
    return TokenResponse(
        user=UserRead(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            is_active=user.is_active,
        ),
        expires_at=expires_at,
    )


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> Response:
    _clear_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@auth_router.get("/me", response_model=UserRead)
def me(current_user: AuthenticatedUser = Depends(get_current_user)) -> UserRead:
    return UserRead(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
        role=current_user.role,
        is_active=current_user.is_active,
    )


def _require_admin(current_user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin_required")
    return current_user


@auth_router.get("/users", response_model=list[UserRead])
def list_users(
    _: AuthenticatedUser = Depends(_require_admin),
    user_service: UserService = Depends(get_user_service),
) -> list[UserRead]:
    return [
        UserRead(id=u.id, email=u.email, display_name=u.display_name, role=u.role, is_active=u.is_active)
        for u in user_service.list_users()
    ]


@auth_router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    _: AuthenticatedUser = Depends(_require_admin),
    user_service: UserService = Depends(get_user_service),
) -> UserRead:
    if user_service.get_by_email(payload.email) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email_taken")
    u = user_service.create_user(
        email=payload.email,
        password=payload.password,
        display_name=payload.display_name,
        role=payload.role,
    )
    return UserRead(id=u.id, email=u.email, display_name=u.display_name, role=u.role, is_active=u.is_active)


@auth_router.patch("/users/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def set_password(
    user_id: UUID,
    payload: UserSetPassword,
    _: AuthenticatedUser = Depends(_require_admin),
    user_service: UserService = Depends(get_user_service),
) -> None:
    if not user_service.set_password(user_id, payload.new_password):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")


@auth_router.patch("/users/{user_id}/active", response_model=UserRead)
def set_active(
    user_id: UUID,
    payload: UserSetActive,
    current_user: AuthenticatedUser = Depends(_require_admin),
    user_service: UserService = Depends(get_user_service),
) -> UserRead:
    if str(user_id) == str(current_user.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cannot_deactivate_self")
    if not user_service.set_active(user_id, active=payload.active):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")
    u = user_service.get_by_id(user_id)
    return UserRead(id=u.id, email=u.email, display_name=u.display_name, role=u.role, is_active=u.is_active)  # type: ignore[union-attr]
