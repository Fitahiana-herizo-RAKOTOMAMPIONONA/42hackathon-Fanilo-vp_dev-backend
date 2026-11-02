from __future__ import annotations

from datetime import datetime, timezone
# pyrefly: ignore[missing-import]
from sqlalchemy import desc, func, select, update
# pyrefly: ignore[missing-import]
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.editorial.models import (
    EditorialArticle,
    EditorialCategory,
    EditorialRating,
    EditorialReview,
    EditorialStatus,
)


class EditorialRepository:

    @staticmethod
    def create(
        session: AsyncSession,
        article: EditorialArticle,
    ) -> None:
        """Ajoute un article à la session."""
        session.add(article)

    @staticmethod
    async def get_by_id(
        session: AsyncSession,
        article_id: int,
    ) -> EditorialArticle | None:
        """Récupère un article par son identifiant unique."""
        result = await session.execute(
            select(EditorialArticle).where(EditorialArticle.id == article_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_slug(
        session: AsyncSession,
        slug: str,
    ) -> EditorialArticle | None:
        """Récupère un article par son slug SEO."""
        result = await session.execute(
            select(EditorialArticle).where(EditorialArticle.slug == slug)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_articles(
        session: AsyncSession,
        page: int = 1,
        per_page: int = 20,
        status: EditorialStatus | None = None,
        category: EditorialCategory | None = None,
        rating: EditorialRating | None = None,
        author_id: int | None = None,
        is_featured: bool | None = None,
        search_query: str | None = None,
        sort_by: str = "recent",
    ) -> tuple[list[EditorialArticle], int]:
        """Liste paginée et filtrée des articles éditoriaux."""
        query = select(EditorialArticle)
        count_query = select(func.count()).select_from(EditorialArticle)

        if status:
            query = query.where(EditorialArticle.status == status)
            count_query = count_query.where(EditorialArticle.status == status)

        if category:
            query = query.where(EditorialArticle.category == category)
            count_query = count_query.where(EditorialArticle.category == category)

        if rating:
            query = query.where(EditorialArticle.editorial_rating == rating)
            count_query = count_query.where(EditorialArticle.editorial_rating == rating)

        if author_id:
            query = query.where(EditorialArticle.author_id == author_id)
            count_query = count_query.where(EditorialArticle.author_id == author_id)

        if is_featured is not None:
            query = query.where(EditorialArticle.is_featured == is_featured)
            count_query = count_query.where(EditorialArticle.is_featured == is_featured)

        if search_query:
            pattern = f"%{search_query.strip()}%"
            condition = (
                EditorialArticle.title.ilike(pattern)
                | EditorialArticle.summary.ilike(pattern)
                | EditorialArticle.content.ilike(pattern)
                | EditorialArticle.fact_check_claim.ilike(pattern)
                | EditorialArticle.tags.ilike(pattern)
            )
            query = query.where(condition)
            count_query = count_query.where(condition)

        # Tri
        if sort_by == "views":
            query = query.order_by(desc(EditorialArticle.views_count))
        elif sort_by == "published":
            query = query.order_by(desc(EditorialArticle.published_at))
        else:
            query = query.order_by(desc(EditorialArticle.created_at))

        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await session.execute(query)
        articles = list(result.scalars().all())

        count_result = await session.execute(count_query)
        total = count_result.scalar_one()

        return articles, total

    @staticmethod
    async def increment_views(
        session: AsyncSession,
        article_id: int,
    ) -> None:
        """Incrémente de manière atomique le compteur de vues d'un article."""
        stmt = (
            update(EditorialArticle)
            .where(EditorialArticle.id == article_id)
            .values(views_count=EditorialArticle.views_count + 1)
        )
        await session.execute(stmt)

    @staticmethod
    async def delete(
        session: AsyncSession,
        article: EditorialArticle,
    ) -> None:
        """Supprime un article."""
        await session.delete(article)

    @staticmethod
    def add_review(
        session: AsyncSession,
        review: EditorialReview,
    ) -> None:
        """Ajoute un log ou commentaire d'examen éditorial."""
        session.add(review)

    @staticmethod
    async def get_reviews(
        session: AsyncSession,
        article_id: int,
    ) -> list[EditorialReview]:
        """Récupère tous les logs de révision d'un article."""
        result = await session.execute(
            select(EditorialReview)
            .where(EditorialReview.article_id == article_id)
            .order_by(desc(EditorialReview.created_at))
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_stats(
        session: AsyncSession,
    ) -> dict:
        """Calcule les statistiques globales pour le tableau de bord éditorial."""
        # Total count
        total = await session.scalar(select(func.count(EditorialArticle.id))) or 0

        # Status counts
        status_counts = {}
        for st in EditorialStatus:
            count = await session.scalar(
                select(func.count(EditorialArticle.id)).where(EditorialArticle.status == st)
            ) or 0
            status_counts[st.value] = count

        # Total views
        total_views = await session.scalar(
            select(func.coalesce(func.sum(EditorialArticle.views_count), 0))
        ) or 0

        # Category breakdown
        cat_result = await session.execute(
            select(EditorialArticle.category, func.count(EditorialArticle.id))
            .group_by(EditorialArticle.category)
        )
        category_breakdown = {row[0].value if hasattr(row[0], "value") else str(row[0]): row[1] for row in cat_result.all()}

        # Rating breakdown
        rating_result = await session.execute(
            select(EditorialArticle.editorial_rating, func.count(EditorialArticle.id))
            .where(EditorialArticle.editorial_rating.is_not(None))
            .group_by(EditorialArticle.editorial_rating)
        )
        rating_breakdown = {
            row[0].value if hasattr(row[0], "value") else str(row[0]): row[1]
            for row in rating_result.all()
        }

        return {
            "total_articles": total,
            "drafts_count": status_counts.get(EditorialStatus.DRAFT.value, 0),
            "in_review_count": status_counts.get(EditorialStatus.IN_REVIEW.value, 0),
            "approved_count": status_counts.get(EditorialStatus.APPROVED.value, 0),
            "published_count": status_counts.get(EditorialStatus.PUBLISHED.value, 0),
            "archived_count": status_counts.get(EditorialStatus.ARCHIVED.value, 0),
            "total_views": int(total_views),
            "category_breakdown": category_breakdown,
            "rating_breakdown": rating_breakdown,
        }
