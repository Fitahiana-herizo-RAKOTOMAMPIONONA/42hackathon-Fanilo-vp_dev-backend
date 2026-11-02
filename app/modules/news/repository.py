from __future__ import annotations

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.news.models import NewsArticle, NewsStatus


class NewsRepository:

    @staticmethod
    def create(
        session: AsyncSession,
        article: NewsArticle,
    ) -> None:
        session.add(article)

    @staticmethod
    def create_many(
        session: AsyncSession,
        articles: list[NewsArticle],
    ) -> None:
        session.add_all(articles)

    @staticmethod
    async def get_by_id(
        session: AsyncSession,
        article_id: int,
    ) -> NewsArticle | None:
        result = await session.execute(
            select(NewsArticle).where(NewsArticle.id == article_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_url(
        session: AsyncSession,
        url: str,
    ) -> NewsArticle | None:
        result = await session.execute(
            select(NewsArticle).where(NewsArticle.source_url == url)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_all(
        session: AsyncSession,
        page: int = 1,
        per_page: int = 20,
        status: NewsStatus | None = None,
    ) -> tuple[list[NewsArticle], int]:
        query = select(NewsArticle)
        count_query = select(func.count()).select_from(NewsArticle)

        if status:
            query = query.where(NewsArticle.status == status)
            count_query = count_query.where(NewsArticle.status == status)

        query = query.order_by(desc(NewsArticle.collected_at))
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await session.execute(query)
        articles = list(result.scalars().all())

        count_result = await session.execute(count_query)
        total = count_result.scalar_one()

        return articles, total

    @staticmethod
    async def search(
        session: AsyncSession,
        query: str,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[NewsArticle], int]:
        search_pattern = f"%{query}%"

        stmt = (
            select(NewsArticle)
            .where(
                NewsArticle.title.ilike(search_pattern)
                | NewsArticle.content.ilike(search_pattern)
            )
            .order_by(desc(NewsArticle.collected_at))
            .offset((page - 1) * per_page)
            .limit(per_page)
        )

        count_stmt = (
            select(func.count())
            .select_from(NewsArticle)
            .where(
                NewsArticle.title.ilike(search_pattern)
                | NewsArticle.content.ilike(search_pattern)
            )
        )

        result = await session.execute(stmt)
        articles = list(result.scalars().all())

        count_result = await session.execute(count_stmt)
        total = count_result.scalar_one()

        return articles, total

    @staticmethod
    async def update_status(
        session: AsyncSession,
        article_id: int,
        status: NewsStatus,
    ) -> NewsArticle | None:
        article = await NewsRepository.get_by_id(session, article_id)
        if article:
            article.status = status
            await session.commit()
            await session.refresh(article)
        return article

    @staticmethod
    async def delete(
        session: AsyncSession,
        article_id: int,
    ) -> bool:
        article = await NewsRepository.get_by_id(session, article_id)
        if article:
            await session.delete(article)
            await session.commit()
            return True
        return False
