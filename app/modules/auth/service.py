from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User, UserRole
from app.modules.auth.repository import UserRepository
from app.modules.auth.schemas import UserRegister
from app.modules.auth.security import (
    create_access_token,
    hash_password,
    verify_password,
)


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class InactiveUserError(Exception):
    pass


class AuthService:

    @staticmethod
    async def register(
        session: AsyncSession,
        data: UserRegister,
    ) -> User:
        try:
            existing_user = await UserRepository.get_by_email(
                session,
                data.email,
            )

            if existing_user:
                raise EmailAlreadyRegisteredError()

            role = getattr(data, "role", UserRole.JOURNALIST) or UserRole.JOURNALIST
            user = User(
                email=data.email,
                password_hash=hash_password(data.password),
                role=role,
            )

            UserRepository.create(session, user)
            await session.commit()
            await session.refresh(user)

            return user

        except IntegrityError as exc:
            await session.rollback()
            raise EmailAlreadyRegisteredError() from exc

    @staticmethod
    async def login(
        session: AsyncSession,
        email: str,
        password: str,
    ) -> tuple[str, User]:
        user = await UserRepository.get_by_email(session, email.strip().lower())

        if user is None or not verify_password(
            password,
            user.password_hash,
        ):
            raise InvalidCredentialsError()

        if not user.is_active:
            raise InactiveUserError()

        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
        token = create_access_token(
            user_id=user.id,
            email=user.email,
            role=role_str,
        )

        return token, user