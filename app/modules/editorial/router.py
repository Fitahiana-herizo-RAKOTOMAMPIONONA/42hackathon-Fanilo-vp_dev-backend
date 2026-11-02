# pyrefly: ignore[missing-import]
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials
# pyrefly: ignore[missing-import]
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.database import get_db
from app.modules.auth.dependency import (
    bearer_scheme,
    get_current_user,
    oauth2_scheme,
)
from app.modules.auth.models import User
from app.modules.editorial.models import (
    EditorialCategory,
    EditorialRating,
    EditorialStatus,
)
from app.modules.editorial.schemas import (
    EditorialArticleCreate,
    EditorialArticleDetailResponse,
    EditorialArticleResponse,
    EditorialArticleUpdate,
    EditorialCommentCreate,
    EditorialDashboardStats,
    EditorialGenerateDraftRequest,
    EditorialListResponse,
    EditorialReviewActionRequest,
    EditorialReviewLogResponse,
)
from app.modules.editorial.service import EditorialService

editorial_router = APIRouter(
    prefix="/editorial",
    tags=["Editorial"],
)


async def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    oauth2_token: str | None = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db),
) -> User | None:
    """Récupère l'utilisateur s'il est connecté, sans bloquer les requêtes publiques."""
    try:
        return await get_current_user(
            credentials=credentials,
            oauth2_token=oauth2_token,
            session=session,
        )
    except HTTPException:
        return None


@editorial_router.post(
    "/articles",
    response_model=EditorialArticleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un brouillon d'article éditorial",
)
async def create_article(
    data: EditorialArticleCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Permet à un journaliste de rédiger et enregistrer un brouillon d'article."""
    return await EditorialService.create_article(
        session=session,
        data=data,
        author=current_user,
    )


@editorial_router.post(
    "/generate-draft",
    response_model=EditorialArticleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Générer automatiquement un brouillon éditorial",
)
async def generate_draft(
    data: EditorialGenerateDraftRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Génère un brouillon structuré à partir d'un article de presse (news_id),
    d'un résultat de vérification (verification_id), d'une URL web ou d'un sujet.
    """
    return await EditorialService.generate_draft_from_source(
        session=session,
        req=data,
        author=current_user,
    )


@editorial_router.get(
    "/articles",
    response_model=EditorialListResponse,
    summary="Lister les articles éditoriaux",
)
async def list_articles(
    page: int = Query(default=1, ge=1, description="Numéro de page"),
    per_page: int = Query(default=20, ge=1, le=100, description="Articles par page"),
    status_filter: EditorialStatus | None = Query(
        default=None,
        alias="status",
        description="Filtrer par statut (réservé aux journalistes/admins pour les non-publiés)",
    ),
    category: EditorialCategory | None = Query(
        default=None,
        description="Filtrer par catégorie",
    ),
    rating: EditorialRating | None = Query(
        default=None,
        description="Filtrer par verdict fact-checking",
    ),
    author_id: int | None = Query(default=None, description="Filtrer par auteur"),
    is_featured: bool | None = Query(default=None, description="Filtrer les articles à la une"),
    search: str | None = Query(default=None, description="Recherche textuelle"),
    sort_by: str = Query(
        default="recent",
        description="Tri : 'recent', 'views', ou 'published'",
    ),
    current_user: User | None = Depends(get_optional_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Liste paginée des articles.
    Le grand public ne voit que les articles avec le statut 'published'.
    Les journalistes et administrateurs connectés peuvent explorer tous les statuts.
    """
    articles, total = await EditorialService.list_articles(
        session=session,
        page=page,
        per_page=per_page,
        status_filter=status_filter,
        category=category,
        rating=rating,
        author_id=author_id,
        is_featured=is_featured,
        search_query=search,
        sort_by=sort_by,
        current_user=current_user,
    )

    return EditorialListResponse(
        total=total,
        page=page,
        per_page=per_page,
        articles=[EditorialArticleResponse.model_validate(a) for a in articles],
    )


@editorial_router.get(
    "/stats",
    response_model=EditorialDashboardStats,
    summary="Statistiques du desk éditorial",
)
async def get_editorial_stats(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Renvoie les métriques éditoriales globales pour le tableau de bord de rédaction."""
    stats = await EditorialService.get_dashboard_stats(session)
    return EditorialDashboardStats(**stats)


@editorial_router.get(
    "/articles/{identifier}",
    response_model=EditorialArticleDetailResponse,
    summary="Consulter le détail d'un article par ID ou Slug",
)
async def get_article_detail(
    identifier: str,
    current_user: User | None = Depends(get_optional_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Récupère le détail d'un article ainsi que l'historique de ses révisions.
    Accepte l'ID numérique ou le slug SEO.
    Incrémente automatiquement le compteur de lectures si l'article est publié.
    """
    article = await EditorialService.get_article(
        session=session,
        identifier=identifier,
        current_user=current_user,
        track_view=True,
    )
    return EditorialArticleDetailResponse.model_validate(article)


@editorial_router.put(
    "/articles/{article_id}",
    response_model=EditorialArticleResponse,
    summary="Mettre à jour un article éditorial",
)
async def update_article(
    article_id: int,
    data: EditorialArticleUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Met à jour le contenu d'un article. Réservé à son auteur ou aux administrateurs."""
    return await EditorialService.update_article(
        session=session,
        article_id=article_id,
        data=data,
        user=current_user,
    )


@editorial_router.post(
    "/articles/{article_id}/submit",
    response_model=EditorialArticleResponse,
    summary="Soumettre l'article au comité de relecture",
)
async def submit_article(
    article_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Passe le statut de l'article de DRAFT à IN_REVIEW."""
    return await EditorialService.submit_for_review(
        session=session,
        article_id=article_id,
        user=current_user,
    )


@editorial_router.post(
    "/articles/{article_id}/review",
    response_model=EditorialArticleResponse,
    summary="Valider ou rejeter un article en relecture",
)
async def review_article(
    article_id: int,
    data: EditorialReviewActionRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Permet au relecteur d'approuver ou de demander des corrections sur l'article."""
    return await EditorialService.review_article(
        session=session,
        article_id=article_id,
        decision=data.decision,
        feedback=data.feedback,
        reviewer=current_user,
    )


@editorial_router.post(
    "/articles/{article_id}/publish",
    response_model=EditorialArticleResponse,
    summary="Publier un article approuvé",
)
async def publish_article(
    article_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Publie l'article pour le rendre accessible publiquement sur le site/l'API."""
    return await EditorialService.publish_article(
        session=session,
        article_id=article_id,
        user=current_user,
    )


@editorial_router.post(
    "/articles/{article_id}/archive",
    response_model=EditorialArticleResponse,
    summary="Archiver un article",
)
async def archive_article(
    article_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Archive un article."""
    return await EditorialService.archive_article(
        session=session,
        article_id=article_id,
        user=current_user,
    )


@editorial_router.delete(
    "/articles/{article_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un article",
)
async def delete_article(
    article_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Supprime un article brouillon ou permet à un administrateur de le retirer."""
    await EditorialService.delete_article(
        session=session,
        article_id=article_id,
        user=current_user,
    )
    return None


@editorial_router.post(
    "/articles/{article_id}/comments",
    response_model=EditorialReviewLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ajouter une note ou commentaire de révision",
)
async def add_editorial_comment(
    article_id: int,
    data: EditorialCommentCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Ajoute une note collaborative dans le fil de discussion de l'article."""
    review = await EditorialService.add_comment(
        session=session,
        article_id=article_id,
        comment_text=data.comment,
        user=current_user,
    )
    return EditorialReviewLogResponse.model_validate(review)


@editorial_router.get(
    "/articles/{article_id}/comments",
    response_model=list[EditorialReviewLogResponse],
    summary="Consulter l'historique des commentaires et révisions",
)
async def get_editorial_comments(
    article_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Récupère tous les échanges et traces d'audit de relecture d'un article."""
    reviews = await EditorialService.get_reviews(
        session=session,
        article_id=article_id,
    )
    return [EditorialReviewLogResponse.model_validate(r) for r in reviews]
