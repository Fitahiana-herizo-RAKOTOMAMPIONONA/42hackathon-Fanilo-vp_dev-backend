from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class NewsCollectRequest(BaseModel):
    """Requête de collecte de news depuis Facebook/Google."""
    query: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Mots-clés ou sujet à rechercher",
    )
    num_results: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Nombre de résultats souhaités",
    )
    source: str = Field(
        default="all",
        description="Source: 'facebook', 'google', ou 'all'",
    )


class NewsCreateManual(BaseModel):
    """Création manuelle d'une news par un journaliste."""
    title: str = Field(..., min_length=5, max_length=500)
    content: str = Field(..., min_length=10)
    source_url: str | None = None
    author: str | None = None
    image_url: str | None = None


class NewsResponse(BaseModel):
    """Réponse d'un article de news."""
    id: int
    title: str
    content: str
    source: str
    source_url: str | None
    author: str | None
    image_url: str | None
    status: str
    collected_by_id: int | None
    published_at: datetime | None
    collected_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NewsCollectResponse(BaseModel):
    """Réponse après collecte de news."""
    collected_count: int
    articles: list[NewsResponse]
    query: str


class NewsListResponse(BaseModel):
    """Liste paginée de news."""
    total: int
    page: int
    per_page: int
    articles: list[NewsResponse]
