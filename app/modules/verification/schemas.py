from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VerifyRequest(BaseModel):
    """L'utilisateur soumet une information à vérifier."""
    claim: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="L'information / affirmation à vérifier",
    )


class VerificationSourceResponse(BaseModel):
    """Une source trouvée pour la vérification."""
    id: int
    source_type: str
    url: str
    title: str
    snippet: str
    supports_claim: bool | None
    relevance_score: float

    model_config = ConfigDict(from_attributes=True)


class VerificationResponse(BaseModel):
    """Résultat complet d'une vérification."""
    id: int
    claim_text: str
    status: str
    verdict: str
    confidence_score: float
    analysis_summary: str | None
    sources_found: int
    sources_supporting: int
    sources_contradicting: int
    sources: list[VerificationSourceResponse]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VerificationListResponse(BaseModel):
    """Liste paginée des vérifications."""
    total: int
    page: int
    per_page: int
    verifications: list[VerificationResponse]
