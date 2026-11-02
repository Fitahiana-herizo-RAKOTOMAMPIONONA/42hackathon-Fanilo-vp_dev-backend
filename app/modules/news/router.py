from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.database import get_db
from app.modules.auth.dependency import get_current_user
from app.modules.auth.models import User
from app.modules.news.models import NewsStatus
from app.modules.news.schemas import (
    NewsCollectRequest,
    NewsCollectResponse,
    NewsCreateManual,
    NewsListResponse,
    NewsResponse,
)
from app.modules.news.service import NewsService


news_router = APIRouter(
    prefix="/news",
    tags=["News"],
)


@news_router.post(
    "/collect",
    response_model=NewsCollectResponse,
    summary="Collecter des news depuis Google et Facebook",
)
async def collect_news(
    data: NewsCollectRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Lance une recherche sur Google et Facebook pour collecter
    les news liées au sujet donné et les stocker en base de données.
    """
    articles = await NewsService.collect_from_search(
        session=session,
        query=data.query,
        num_results=data.num_results,
        source=data.source,
        user_id=current_user.id,
    )

    return NewsCollectResponse(
        collected_count=len(articles),
        articles=[NewsResponse.model_validate(a) for a in articles],
        query=data.query,
    )


@news_router.post(
    "/",
    response_model=NewsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ajouter une news manuellement",
)
async def create_news(
    data: NewsCreateManual,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Permet à un journaliste de créer manuellement un article."""
    article = await NewsService.create_manual(
        session=session,
        data=data,
        user_id=current_user.id,
    )
    return article


@news_router.get(
    "/",
    response_model=NewsListResponse,
    summary="Lister les news collectées",
)
async def list_news(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    status_filter: NewsStatus | None = Query(
        default=None,
        alias="status",
        description="Filtrer par statut: pending, verified, fake, unverified",
    ),
    session: AsyncSession = Depends(get_db),
):
    """Liste paginée de tous les articles collectés."""
    articles, total = await NewsService.list_articles(
        session=session,
        page=page,
        per_page=per_page,
        status=status_filter,
    )

    return NewsListResponse(
        total=total,
        page=page,
        per_page=per_page,
        articles=[NewsResponse.model_validate(a) for a in articles],
    )


@news_router.get(
    "/search",
    response_model=NewsListResponse,
    summary="Rechercher dans les news stockées",
)
async def search_news(
    q: str = Query(..., min_length=2, description="Terme de recherche"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    """Recherche plein texte dans les news stockées en base."""
    articles, total = await NewsService.search_articles(
        session=session,
        query=q,
        page=page,
        per_page=per_page,
    )

    return NewsListResponse(
        total=total,
        page=page,
        per_page=per_page,
        articles=[NewsResponse.model_validate(a) for a in articles],
    )


@news_router.get(
    "/{article_id}",
    response_model=NewsResponse,
    summary="Détail d'un article de news",
)
async def get_news(
    article_id: int,
    session: AsyncSession = Depends(get_db),
):
    article = await NewsService.get_article(session, article_id)
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found",
        )
    return article


@news_router.patch(
    "/{article_id}/status",
    response_model=NewsResponse,
    summary="Mettre à jour le statut d'un article",
)
async def update_news_status(
    article_id: int,
    new_status: NewsStatus,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Change le statut d'un article (pending → verified/fake/unverified)."""
    article = await NewsService.update_status(session, article_id, new_status)
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found",
        )
    return article


@news_router.delete(
    "/{article_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un article",
)
async def delete_news(
    article_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    deleted = await NewsService.delete_article(session, article_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found",
        )
