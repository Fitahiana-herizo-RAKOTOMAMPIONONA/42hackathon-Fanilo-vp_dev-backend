import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
    OAuth2PasswordBearer,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.database import get_db
from app.modules.auth.models import User, UserRole
from app.modules.auth.repository import UserRepository
from app.modules.auth.security import decode_access_token


bearer_scheme = HTTPBearer(auto_error=False)
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/token",
    auto_error=False,
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    oauth2_token: str | None = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token: str | None = None
    if credentials is not None:
        token = credentials.credentials
    elif oauth2_token is not None:
        token = oauth2_token

    if not token:
        raise unauthorized

    # Tolérer si le token contient le préfixe "Bearer "
    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    try:
        payload = decode_access_token(token)

        if payload.get("type") != "access":
            raise unauthorized

        user_id = int(payload["sub"])

    except (jwt.InvalidTokenError, ValueError, KeyError):
        raise unauthorized

    user = await UserRepository.get_by_id(session, user_id)

    if user is None:
        raise unauthorized

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    return user


def require_roles(*allowed_roles: UserRole):
    """Dépendance pour vérifier les rôles autorisés."""
    async def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted for your role",
            )
        return current_user

    return role_checker


require_admin = require_roles(UserRole.ADMIN)
require_journalist = require_roles(UserRole.JOURNALIST, UserRole.ADMIN)