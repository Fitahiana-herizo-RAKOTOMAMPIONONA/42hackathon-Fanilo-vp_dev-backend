from __future__ import annotations

import logging
import re
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.external_apis.scraper import (
    ScrapedResult,
    search_and_verify,
)
from app.modules.verification.models import (
    VerificationRequest,
    VerificationSource,
    VerificationStatus,
    VerificationVerdict,
)
from app.modules.verification.repository import VerificationRepository

logger = logging.getLogger(__name__)

# Mots-clés indiquant une contestation / fake news
_DEBUNK_KEYWORDS = {
    "faux", "fake", "intox", "infox", "dément", "démenti", "mensonge",
    "fake news", "trompeur", "canular", "hoax", "fausse", "infondé",
    "rumeur", "contredit", "pas vrai", "erroné", "démentie", "fabrication",
}

# Mots-clés indiquant une confirmation / vérité
_CONFIRM_KEYWORDS = {
    "vrai", "confirme", "avéré", "authentique", "confirmé", "officiel",
    "effectivement", "vérité", "prouvé", "attesté", "confirmée", "exact",
}


def _tokenize(text: str) -> set[str]:
    """Extrait les mots significatifs (longueur >= 4) en minuscules."""
    words = re.findall(r"\b\w{4,}\b", text.lower())
    # Stopwords français/anglais très fréquents
    stopwords = {
        "dans", "pour", "avec", "cette", "sont", "leur", "plus", "tout",
        "tous", "fait", "mais", "comme", "aussi", "bien", "être", "avoir",
        "faire", "about", "from", "that", "this", "with", "have", "were",
    }
    return {w for w in words if w not in stopwords}


def _compute_relevance(claim_words: set[str], text: str) -> float:
    """Calcule un score de pertinence basé sur le chevauchement de mots-clés."""
    if not claim_words:
        return 0.0
    text_words = set(re.findall(r"\b\w{4,}\b", text.lower()))
    overlap = claim_words.intersection(text_words)
    return round(min(1.0, len(overlap) / max(len(claim_words), 1)), 2)


def _evaluate_source_stance(snippet_or_title: str) -> bool | None:
    """
    Évalue si la source semble soutenir (True), contredire (False)
    ou est neutre/inconnu (None) par rapport à l'affirmation.
    """
    text_lower = snippet_or_title.lower()

    has_debunk = any(k in text_lower for k in _DEBUNK_KEYWORDS)
    has_confirm = any(k in text_lower for k in _CONFIRM_KEYWORDS)

    if has_debunk and not has_confirm:
        return False
    if has_confirm and not has_debunk:
        return True
    return None


class VerificationService:

    @staticmethod
    async def verify_claim(
        session: AsyncSession,
        claim: str,
        user_id: int,
    ) -> VerificationRequest:
        """
        Vérifie une affirmation en interrogeant Google et Facebook,
        analyse les sources trouvées et attribue un verdict.
        """
        # 1. Créer la demande initiale
        req = VerificationRequest(
            claim_text=claim,
            user_id=user_id,
            status=VerificationStatus.PROCESSING,
            verdict=VerificationVerdict.UNVERIFIED,
            confidence_score=0.0,
        )
        VerificationRepository.create(session, req)
        await session.commit()
        await session.refresh(req)

        try:
            # 2. Scraper Google et Facebook
            results: list[ScrapedResult] = await search_and_verify(
                claim=claim,
                num_results=10,
            )

            claim_words = _tokenize(claim)

            supporting_count = 0
            contradicting_count = 0
            sources_to_add: list[VerificationSource] = []

            for r in results:
                full_text = f"{r.title} {r.snippet}"
                relevance = _compute_relevance(claim_words, full_text)
                stance = _evaluate_source_stance(full_text)

                if stance is True:
                    supporting_count += 1
                elif stance is False:
                    contradicting_count += 1

                source_record = VerificationSource(
                    verification_id=req.id,
                    source_type=r.source,
                    url=r.url[:2000],
                    title=r.title[:500] if r.title else "Sans titre",
                    snippet=r.snippet[:2000] if r.snippet else "",
                    supports_claim=stance,
                    relevance_score=relevance,
                )
                sources_to_add.append(source_record)

            # Enregistrer les sources
            for s in sources_to_add:
                VerificationRepository.add_source(session, s)

            total_sources = len(sources_to_add)

            # 3. Calculer le verdict et score de confiance
            if total_sources == 0:
                verdict = VerificationVerdict.INSUFFICIENT_DATA
                confidence = 0.0
                summary = (
                    "Aucune source pertinente trouvée sur Google ou Facebook "
                    "pour corroborer ou infirmer cette affirmation."
                )
            elif contradicting_count > supporting_count:
                verdict = VerificationVerdict.LIKELY_FALSE
                confidence = round(
                    min(0.95, (contradicting_count / total_sources) * 0.7 + 0.3), 2
                )
                summary = (
                    f"Information probablement fausse. Sur {total_sources} sources "
                    f"analysées, {contradicting_count} contestent l'affirmation."
                )
            elif supporting_count > contradicting_count:
                verdict = VerificationVerdict.LIKELY_TRUE
                confidence = round(
                    min(0.95, (supporting_count / total_sources) * 0.7 + 0.3), 2
                )
                summary = (
                    f"Information probablement vraie. Sur {total_sources} sources "
                    f"analysées, {supporting_count} confirment l'affirmation."
                )
            elif supporting_count > 0 and supporting_count == contradicting_count:
                verdict = VerificationVerdict.MIXED
                confidence = 0.50
                summary = (
                    f"Avis partagés. {supporting_count} sources confirment et "
                    f"{contradicting_count} contestent cette information."
                )
            else:
                verdict = VerificationVerdict.INSUFFICIENT_DATA
                confidence = 0.25
                summary = (
                    f"{total_sources} sources identifiées mais sans consensus clair "
                    f"sur la véracité de l'information."
                )

            # 4. Mettre à jour la demande de vérification
            req.status = VerificationStatus.COMPLETED
            req.verdict = verdict
            req.confidence_score = confidence
            req.analysis_summary = summary
            req.sources_found = total_sources
            req.sources_supporting = supporting_count
            req.sources_contradicting = contradicting_count

            await session.commit()
            await session.refresh(req)

        except Exception as exc:
            logger.exception("Erreur lors de la vérification de l'affirmation: %s", exc)
            req.status = VerificationStatus.FAILED
            req.analysis_summary = f"Échec de l'analyse : {str(exc)}"
            await session.commit()
            await session.refresh(req)

        return req

    @staticmethod
    async def get_by_id(
        session: AsyncSession,
        verification_id: int,
    ) -> VerificationRequest | None:
        return await VerificationRepository.get_by_id(session, verification_id)

    @staticmethod
    async def list_by_user(
        session: AsyncSession,
        user_id: int,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[VerificationRequest], int]:
        return await VerificationRepository.list_by_user(
            session=session,
            user_id=user_id,
            page=page,
            per_page=per_page,
        )

    @staticmethod
    async def list_all(
        session: AsyncSession,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[VerificationRequest], int]:
        return await VerificationRepository.list_all(
            session=session,
            page=page,
            per_page=per_page,
        )

    @staticmethod
    async def delete(
        session: AsyncSession,
        verification_id: int,
        user_id: int | None = None,
    ) -> bool:
        verification = await VerificationRepository.get_by_id(
            session, verification_id
        )
        if not verification:
            return False
        if user_id is not None and verification.user_id != user_id:
            return False
        return await VerificationRepository.delete(session, verification_id)
