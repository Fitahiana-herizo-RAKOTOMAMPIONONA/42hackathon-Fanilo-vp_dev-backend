import pytest
from app.modules.editorial.service import slugify
from app.modules.editorial.models import EditorialStatus, EditorialRating, EditorialCategory


def test_slugify():
    assert slugify("L'intelligence artificielle va-t-elle remplacer les journalistes ?") == "lintelligence-artificielle-va-t-elle-remplacer-les-journalistes"
    assert slugify("Madagascar : Nouveau vaccin validé par l'OMS !") == "madagascar-nouveau-vaccin-valide-par-loms"
    assert slugify("   Espaces et caractères spéciaux @#$%^&*()   ") == "espaces-et-caracteres-speciaux"
    assert slugify("") == "article"


def test_editorial_enums():
    assert EditorialStatus.DRAFT.value == "draft"
    assert EditorialStatus.IN_REVIEW.value == "in_review"
    assert EditorialStatus.APPROVED.value == "approved"
    assert EditorialStatus.PUBLISHED.value == "published"
    assert EditorialStatus.REJECTED.value == "rejected"
    assert EditorialStatus.ARCHIVED.value == "archived"

    assert EditorialRating.TRUE.value == "true"
    assert EditorialRating.FALSE.value == "false"
    assert EditorialRating.MISLEADING.value == "misleading"

    assert EditorialCategory.POLITICS.value == "politique"
    assert EditorialCategory.HEALTH.value == "sante"
    assert EditorialCategory.ENVIRONMENT.value == "environnement"
