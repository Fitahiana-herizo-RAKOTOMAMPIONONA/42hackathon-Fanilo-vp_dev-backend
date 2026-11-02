from __future__ import annotations

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.verification.models import (
    VerificationRequest,
    VerificationSource,
)


class VerificationRepository:

    @staticmethod
    def create(
        session: AsyncSession,
        verification: VerificationRequest,
    ) -> None:
        session.add(verification)

    @staticmethod
    async def get_by_id(
        session: AsyncSession,
        verification_id: int,
    ) -> VerificationRequest | None:
        result = await session.execute(
            select(VerificationRequest)
            .options(selectinload(VerificationRequest.sources))
            .where(VerificationRequest.id == verification_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_user(
        session: AsyncSession,
        user_id: int,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[VerificationRequest], int]:
        query = (
            select(VerificationRequest)
            .options(selectinload(VerificationRequest.sources))
            .where(VerificationRequest.user_id == user_id)
            .order_by(desc(VerificationRequest.created_at))
            .offset((page - 1) * per_page)
            .limit(per_page)
        )

        count_query = (
            select(func.count())
            .select_from(VerificationRequest)
            .where(VerificationRequest.user_id == user_id)
        )

        result = await session.execute(query)
        verifications = list(result.scalars().all())

        count_result = await session.execute(count_query)
        total = count_result.scalar_one()

        return verifications, total

    @staticmethod
    async def list_all(
        session: AsyncSession,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[VerificationRequest], int]:
        query = (
            select(VerificationRequest)
            .options(selectinload(VerificationRequest.sources))
            .order_by(desc(VerificationRequest.created_at))
            .offset((page - 1) * per_page)
            .limit(per_page)
        )

        count_query = (
            select(func.count())
            .select_from(VerificationRequest)
        )

        result = await session.execute(query)
        verifications = list(result.scalars().all())

        count_result = await session.execute(count_query)
        total = count_result.scalar_one()

        return verifications, total

    @staticmethod
    def add_source(
        session: AsyncSession,
        source: VerificationSource,
    ) -> None:
        session.add(source)

    @staticmethod
    async def delete(
        session: AsyncSession,
        verification_id: int,
    ) -> bool:
        verification = await VerificationRepository.get_by_id(
            session, verification_id
        )
        if verification:
            await session.delete(verification)
            await session.commit()
            return True
        return False
