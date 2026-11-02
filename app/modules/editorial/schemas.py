from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from app.modules.editorial.models import (
    EditorialCategory,
    EditorialRating,
    EditorialStatus,
)


class EditorialReviewLogResponse(BaseModel):
    """Log ou commentaire d'un examen éditorial."""
    id: int
    article_id: int
    user_id: int
    action: str
    comment: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EditorialArticleCreate(BaseModel):
    """Création d'un brouillon d'article éditorial."""
    title: str = Field(..., min_length=5, max_length=500, description="Titre de l'article")
    summary: str | None = Field(default=None, description="Chapeau ou résumé éditorial")
    content: str = Field(..., min_length=20, description="Contenu complet de l'article")
    fact_check_claim: str | None = Field(default=None, description="Affirmation vérifiée si applicable")
    editorial_rating: EditorialRating | None = Field(
        default=None,
        description="Verdict éditorial (true, false, misleading, etc.)",
    )
    category: EditorialCategory = Field(
        default=EditorialCategory.GENERAL,
        description="Catégorie thématique",
    )
    tags: str | None = Field(default=None, description="Tags séparés par des virgules")
    featured_image_url: str | None = Field(default=None, description="URL de l'image de couverture")
    linked_news_id: int | None = Field(default=None, description="ID de l'article d'actualité source")
    linked_verification_id: int | None = Field(default=None, description="ID de la vérification source")
    is_featured: bool = Field(default=False, description="Mettre en avant sur la page d'accueil")


class EditorialArticleUpdate(BaseModel):
    """Mise à jour d'un article éditorial."""
    title: str | None = Field(default=None, min_length=5, max_length=500)
    summary: str | None = None
    content: str | None = Field(default=None, min_length=20)
    fact_check_claim: str | None = None
    editorial_rating: EditorialRating | None = None
    category: EditorialCategory | None = None
    tags: str | None = None
    featured_image_url: str | None = None
    linked_news_id: int | None = None
    linked_verification_id: int | None = None
    is_featured: bool | None = None


class EditorialReviewActionRequest(BaseModel):
    """Action d'approbation ou de rejet d'un article en relecture."""
    decision: str = Field(
        ...,
        description="Décision de relecture : 'approve' pour approuver, 'reject' pour demander des corrections",
    )
    feedback: str | None = Field(
        default=None,
        description="Commentaire ou motif du rejet / validation",
    )


class EditorialCommentCreate(BaseModel):
    """Ajout d'une note ou commentaire collaboratif sur l'article."""
    comment: str = Field(..., min_length=1, max_length=2000, description="Commentaire de révision")


class EditorialGenerateDraftRequest(BaseModel):
    """Génération automatique d'un brouillon d'article à partir d'une source existante ou scrapée."""
    news_id: int | None = Field(default=None, description="ID d'un article existant dans le module news")
    verification_id: int | None = Field(default=None, description="ID d'une vérification existante")
    source_url: str | None = Field(default=None, description="URL web externe à scraper pour rédiger")
    topic: str | None = Field(default=None, description="Sujet ou affirmation pour recherche web automatique")
    category: EditorialCategory = Field(default=EditorialCategory.GENERAL)


class EditorialArticleResponse(BaseModel):
    """Réponse d'un article éditorial."""
    id: int
    title: str
    slug: str
    summary: str | None
    content: str
    fact_check_claim: str | None
    editorial_rating: EditorialRating | None
    category: EditorialCategory
    tags: str | None
    featured_image_url: str | None
    status: EditorialStatus
    author_id: int | None
    reviewer_id: int | None
    linked_news_id: int | None
    linked_verification_id: int | None
    review_feedback: str | None
    is_featured: bool
    views_count: int
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EditorialArticleDetailResponse(EditorialArticleResponse):
    """Détail complet d'un article avec historique des révisions."""
    reviews: list[EditorialReviewLogResponse] = []


class EditorialListResponse(BaseModel):
    """Liste paginée d'articles éditoriaux."""
    total: int
    page: int
    per_page: int
    articles: list[EditorialArticleResponse]


class EditorialDashboardStats(BaseModel):
    """Statistiques du tableau de bord éditorial."""
    total_articles: int
    drafts_count: int
    in_review_count: int
    approved_count: int
    published_count: int
    archived_count: int
    total_views: int
    category_breakdown: dict[str, int]
    rating_breakdown: dict[str, int]
