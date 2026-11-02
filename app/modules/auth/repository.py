from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User


class UserRepository:

    @staticmethod
    async def get_by_email(
        session: AsyncSession,
        email: str,
    ) -> User | None:
        result = await session.execute(
            select(User).where(User.email == email)
        )

        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id(
        session: AsyncSession,
        user_id: int,
    ) -> User | None:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )

        return result.scalar_one_or_none()

    @staticmethod
    def create(
        session: AsyncSession,
        user: User,
    ) -> None:
        session.add(user)