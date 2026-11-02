from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.external_apis.scraper import (
    ScrapedResult,
    scrape_page_content,
    search_facebook,
    search_google,
)
from app.modules.news.models import NewsArticle, NewsSource, NewsStatus
from app.modules.news.repository import NewsRepository
from app.modules.news.schemas import NewsCreateManual

logger = logging.getLogger(__name__)


class NewsService:

    @staticmethod
    async def collect_from_search(
        session: AsyncSession,
        query: str,
        num_results: int = 10,
        source: str = "all",
        user_id: int | None = None,
    ) -> list[NewsArticle]:
        """
        Collecte des news depuis Google et/ou Facebook et les stocke en DB.
        """
        results: list[ScrapedResult] = []

        if source in ("all", "google"):
            google_results = await search_google(query, num_results=num_results)
            results.extend(google_results)

        if source in ("all", "facebook"):
            fb_results = await search_facebook(query, num_results=num_results)
            results.extend(fb_results)

        # Dédupliquer par URL
        seen_urls: set[str] = set()
        unique_results: list[ScrapedResult] = []
        for r in results:
            normalized = r.url.rstrip("/").lower()
            if normalized not in seen_urls:
                seen_urls.add(normalized)
                unique_results.append(r)

        articles: list[NewsArticle] = []
        newly_created: list[NewsArticle] = []

        for result in unique_results:
            # Vérifier si l'article existe déjà en DB
            existing = await NewsRepository.get_by_url(session, result.url)
            if existing:
                articles.append(existing)
                continue

            # Scraper le contenu complet de la page
            page_content = await scrape_page_content(result.url)

            content = result.snippet
            image_url = None
            author = None
            published_at = None

            if page_content:
                content = page_content.content or result.snippet
                image_url = page_content.image_url
                author = page_content.author
                if page_content.published_date:
                    try:
                        published_at = datetime.fromisoformat(
                            page_content.published_date.replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        pass

            # Déterminer la source
            news_source = NewsSource.WEB
            if "facebook.com" in result.url:
                news_source = NewsSource.FACEBOOK
            elif result.source == "google":
                news_source = NewsSource.GOOGLE

            article = NewsArticle(
                title=result.title[:500] if result.title else query[:500],
                content=content[:5000] if content else "",
                source=news_source,
                source_url=result.url[:2000],
                author=author,
                image_url=image_url,
                status=NewsStatus.PENDING,
                collected_by_id=user_id,
                published_at=published_at,
            )

            NewsRepository.create(session, article)
            newly_created.append(article)
            articles.append(article)

        if newly_created:
            try:
                await session.commit()
                for article in newly_created:
                    await session.refresh(article)
            except Exception:
                await session.rollback()
                raise

        return articles

    @staticmethod
    async def create_manual(
        session: AsyncSession,
        data: NewsCreateManual,
        user_id: int,
    ) -> NewsArticle:
        """Création manuelle d'une news par un journaliste."""
        article = NewsArticle(
            title=data.title,
            content=data.content,
            source=NewsSource.MANUAL,
            source_url=data.source_url,
            author=data.author,
            image_url=data.image_url,
            status=NewsStatus.PENDING,
            collected_by_id=user_id,
        )

        NewsRepository.create(session, article)
        await session.commit()
        await session.refresh(article)

        return article

    @staticmethod
    async def get_article(
        session: AsyncSession,
        article_id: int,
    ) -> NewsArticle | None:
        return await NewsRepository.get_by_id(session, article_id)

    @staticmethod
    async def list_articles(
        session: AsyncSession,
        page: int = 1,
        per_page: int = 20,
        status: NewsStatus | None = None,
    ) -> tuple[list[NewsArticle], int]:
        return await NewsRepository.list_all(session, page, per_page, status)

    @staticmethod
    async def search_articles(
        session: AsyncSession,
        query: str,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[NewsArticle], int]:
        return await NewsRepository.search(session, query, page, per_page)

    @staticmethod
    async def update_status(
        session: AsyncSession,
        article_id: int,
        status: NewsStatus,
    ) -> NewsArticle | None:
        return await NewsRepository.update_status(session, article_id, status)

    @staticmethod
    async def delete_article(
        session: AsyncSession,
        article_id: int,
    ) -> bool:
        return await NewsRepository.delete(session, article_id)
