from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timezone

# pyrefly: ignore[missing-import]
from fastapi import HTTPException, status
# pyrefly: ignore[missing-import]
from sqlalchemy.ext.asyncio import AsyncSession
# pyrefly: ignore[missing-import]
from sqlalchemy import select

from app.infrastructure.external_apis.scraper import (
    scrape_page_content,
    search_and_verify,
)
from app.modules.auth.models import User, UserRole
from app.modules.news.models import NewsArticle
from app.modules.verification.models import (
    VerificationRequest,
    VerificationSource,
    VerificationVerdict,
)
from app.modules.editorial.models import (
    EditorialArticle,
    EditorialCategory,
    EditorialRating,
    EditorialReview,
    EditorialStatus,
)
from app.modules.editorial.repository import EditorialRepository
from app.modules.editorial.schemas import (
    EditorialArticleCreate,
    EditorialArticleUpdate,
    EditorialGenerateDraftRequest,
)

logger = logging.getLogger(__name__)


def slugify(value: str) -> str:
    """Génère un slug SEO propre et sans accents."""
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    slug = re.sub(r"[-\s]+", "-", text)
    return slug[:100] if slug else "article"


class EditorialService:

    @staticmethod
    async def _generate_unique_slug(session: AsyncSession, title: str) -> str:
        """Garantit l'unicité du slug généré."""
        base_slug = slugify(title)
        slug = base_slug
        counter = 1

        while await EditorialRepository.get_by_slug(session, slug):
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug

    @staticmethod
    async def create_article(
        session: AsyncSession,
        data: EditorialArticleCreate,
        author: User,
    ) -> EditorialArticle:
        """Crée un nouvel article éditorial à l'état de brouillon (DRAFT)."""
        slug = await EditorialService._generate_unique_slug(session, data.title)

        article = EditorialArticle(
            title=data.title,
            slug=slug,
            summary=data.summary,
            content=data.content,
            fact_check_claim=data.fact_check_claim,
            editorial_rating=data.editorial_rating,
            category=data.category,
            tags=data.tags,
            featured_image_url=data.featured_image_url,
            status=EditorialStatus.DRAFT,
            author_id=author.id,
            linked_news_id=data.linked_news_id,
            linked_verification_id=data.linked_verification_id,
            is_featured=data.is_featured,
        )

        EditorialRepository.create(session, article)
        await session.flush()

        # Log initial de création
        review_log = EditorialReview(
            article_id=article.id,
            user_id=author.id,
            action="created",
            comment="Création du brouillon éditorial.",
        )
        EditorialRepository.add_review(session, review_log)

        await session.commit()
        await session.refresh(article)
        return article

    @staticmethod
    async def update_article(
        session: AsyncSession,
        article_id: int,
        data: EditorialArticleUpdate,
        user: User,
    ) -> EditorialArticle:
        """Met à jour les informations d'un article éditorial."""
        article = await EditorialRepository.get_by_id(session, article_id)
        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article éditorial introuvable.",
            )

        # Vérification des droits : Seul l'auteur ou un admin peut modifier
        if article.author_id != user.id and user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous n'êtes pas autorisé à modifier cet article.",
            )

        # Si l'article est déjà publié, seul un admin peut le modifier directement
        if article.status == EditorialStatus.PUBLISHED and user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Un article publié ne peut être modifié que par un administrateur.",
            )

        if data.title and data.title != article.title:
            article.title = data.title
            article.slug = await EditorialService._generate_unique_slug(session, data.title)

        if data.summary is not None:
            article.summary = data.summary
        if data.content is not None:
            article.content = data.content
        if data.fact_check_claim is not None:
            article.fact_check_claim = data.fact_check_claim
        if data.editorial_rating is not None:
            article.editorial_rating = data.editorial_rating
        if data.category is not None:
            article.category = data.category
        if data.tags is not None:
            article.tags = data.tags
        if data.featured_image_url is not None:
            article.featured_image_url = data.featured_image_url
        if data.linked_news_id is not None:
            article.linked_news_id = data.linked_news_id
        if data.linked_verification_id is not None:
            article.linked_verification_id = data.linked_verification_id
        if data.is_featured is not None:
            article.is_featured = data.is_featured

        # Log de modification
        review_log = EditorialReview(
            article_id=article.id,
            user_id=user.id,
            action="updated",
            comment="Mise à jour du contenu de l'article.",
        )
        EditorialRepository.add_review(session, review_log)

        await session.commit()
        await session.refresh(article)
        return article

    @staticmethod
    async def submit_for_review(
        session: AsyncSession,
        article_id: int,
        user: User,
    ) -> EditorialArticle:
        """Soumet un article pour relecture par le comité de rédaction."""
        article = await EditorialRepository.get_by_id(session, article_id)
        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article éditorial introuvable.",
            )

        if article.author_id != user.id and user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Seul l'auteur ou un administrateur peut soumettre cet article.",
            )

        if article.status not in (EditorialStatus.DRAFT, EditorialStatus.REJECTED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"L'article ne peut pas être soumis (statut actuel: {article.status.value}).",
            )

        article.status = EditorialStatus.IN_REVIEW
        article.review_feedback = None

        review_log = EditorialReview(
            article_id=article.id,
            user_id=user.id,
            action="submitted",
            comment="Article soumis pour relecture éditoriale.",
        )
        EditorialRepository.add_review(session, review_log)

        await session.commit()
        await session.refresh(article)
        return article

    @staticmethod
    async def review_article(
        session: AsyncSession,
        article_id: int,
        decision: str,
        feedback: str | None,
        reviewer: User,
    ) -> EditorialArticle:
        """Approuve ou rejette un article en attente de relecture."""
        article = await EditorialRepository.get_by_id(session, article_id)
        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article éditorial introuvable.",
            )

        if article.status != EditorialStatus.IN_REVIEW:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cet article n'est pas en attente de relecture (statut: {article.status.value}).",
            )

        clean_decision = decision.strip().lower()
        if clean_decision not in ("approve", "reject"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La décision doit être 'approve' ou 'reject'.",
            )

        if clean_decision == "approve":
            article.status = EditorialStatus.APPROVED
            article.reviewer_id = reviewer.id
            article.review_feedback = feedback
            action_name = "approved"
            comment_text = feedback or "Article approuvé par la rédaction."
        else:
            article.status = EditorialStatus.REJECTED
            article.reviewer_id = reviewer.id
            article.review_feedback = feedback
            action_name = "rejected"
            comment_text = feedback or "Corrections demandées par le relecteur."

        review_log = EditorialReview(
            article_id=article.id,
            user_id=reviewer.id,
            action=action_name,
            comment=comment_text,
        )
        EditorialRepository.add_review(session, review_log)

        await session.commit()
        await session.refresh(article)
        return article

    @staticmethod
    async def publish_article(
        session: AsyncSession,
        article_id: int,
        user: User,
    ) -> EditorialArticle:
        """Publie officiellement un article approuvé ou en cours."""
        article = await EditorialRepository.get_by_id(session, article_id)
        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article éditorial introuvable.",
            )

        # Seul un admin ou l'auteur si l'article est approuvé peut publier
        if user.role != UserRole.ADMIN and article.status != EditorialStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="L'article doit être approuvé avant d'être publié.",
            )

        article.status = EditorialStatus.PUBLISHED
        article.published_at = datetime.now(timezone.utc)

        review_log = EditorialReview(
            article_id=article.id,
            user_id=user.id,
            action="published",
            comment="Article officiellement publié.",
        )
        EditorialRepository.add_review(session, review_log)

        await session.commit()
        await session.refresh(article)
        return article

    @staticmethod
    async def archive_article(
        session: AsyncSession,
        article_id: int,
        user: User,
    ) -> EditorialArticle:
        """Archive un article éditorial."""
        article = await EditorialRepository.get_by_id(session, article_id)
        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article éditorial introuvable.",
            )

        if article.author_id != user.id and user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissions insuffisantes pour archiver cet article.",
            )

        article.status = EditorialStatus.ARCHIVED

        review_log = EditorialReview(
            article_id=article.id,
            user_id=user.id,
            action="archived",
            comment="Article archivé.",
        )
        EditorialRepository.add_review(session, review_log)

        await session.commit()
        await session.refresh(article)
        return article

    @staticmethod
    async def delete_article(
        session: AsyncSession,
        article_id: int,
        user: User,
    ) -> bool:
        """Supprime définitivement un article (autorisé en DRAFT ou pour admin)."""
        article = await EditorialRepository.get_by_id(session, article_id)
        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article éditorial introuvable.",
            )

        if user.role != UserRole.ADMIN and (
            article.author_id != user.id or article.status != EditorialStatus.DRAFT
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Seuls les brouillons peuvent être supprimés par leur auteur. Contactez un administrateur.",
            )

        await EditorialRepository.delete(session, article)
        await session.commit()
        return True

    @staticmethod
    async def get_article(
        session: AsyncSession,
        identifier: str,
        current_user: User | None = None,
        track_view: bool = False,
    ) -> EditorialArticle:
        """Récupère un article par son ID numérique ou son slug SEO."""
        article: EditorialArticle | None = None

        if identifier.isdigit():
            article = await EditorialRepository.get_by_id(session, int(identifier))
        if not article:
            article = await EditorialRepository.get_by_slug(session, identifier)

        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article éditorial introuvable.",
            )

        # Si l'article n'est pas encore publié, seuls les journalistes/admins ou l'auteur peuvent le voir
        if article.status != EditorialStatus.PUBLISHED:
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Article non disponible.",
                )
            if current_user.role not in (UserRole.ADMIN, UserRole.JOURNALIST) and article.author_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Accès non autorisé à cet article non publié.",
                )

        # Incrémenter les vues pour les articles publiés
        if track_view and article.status == EditorialStatus.PUBLISHED:
            await EditorialRepository.increment_views(session, article.id)
            await session.commit()
            await session.refresh(article)

        return article

    @staticmethod
    async def list_articles(
        session: AsyncSession,
        page: int = 1,
        per_page: int = 20,
        status_filter: EditorialStatus | None = None,
        category: EditorialCategory | None = None,
        rating: EditorialRating | None = None,
        author_id: int | None = None,
        is_featured: bool | None = None,
        search_query: str | None = None,
        sort_by: str = "recent",
        current_user: User | None = None,
    ) -> tuple[list[EditorialArticle], int]:
        """Liste les articles avec gestion des droits d'affichage."""
        # Pour les utilisateurs non authentifiés ou sans rôle journalist/admin,
        # forcer l'affichage uniquement des articles publiés.
        effective_status = status_filter
        if not current_user or (current_user.role not in (UserRole.ADMIN, UserRole.JOURNALIST)):
            effective_status = EditorialStatus.PUBLISHED

        return await EditorialRepository.list_articles(
            session=session,
            page=page,
            per_page=per_page,
            status=effective_status,
            category=category,
            rating=rating,
            author_id=author_id,
            is_featured=is_featured,
            search_query=search_query,
            sort_by=sort_by,
        )

    @staticmethod
    async def add_comment(
        session: AsyncSession,
        article_id: int,
        comment_text: str,
        user: User,
    ) -> EditorialReview:
        """Ajoute un commentaire collaboratif sur un article."""
        article = await EditorialRepository.get_by_id(session, article_id)
        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article éditorial introuvable.",
            )

        review = EditorialReview(
            article_id=article.id,
            user_id=user.id,
            action="comment",
            comment=comment_text.strip(),
        )
        EditorialRepository.add_review(session, review)
        await session.commit()
        await session.refresh(review)
        return review

    @staticmethod
    async def get_reviews(
        session: AsyncSession,
        article_id: int,
    ) -> list[EditorialReview]:
        """Récupère l'historique de relecture d'un article."""
        return await EditorialRepository.get_reviews(session, article_id)

    @staticmethod
    async def get_dashboard_stats(session: AsyncSession) -> dict:
        """Récupère les statistiques pour la rédaction éditoriale."""
        return await EditorialRepository.get_stats(session)

    @staticmethod
    async def generate_draft_from_source(
        session: AsyncSession,
        req: EditorialGenerateDraftRequest,
        author: User,
    ) -> EditorialArticle:
        """
        Génère automatiquement une ébauche d'article éditorial structuré
        à partir d'une actualité (news_id), d'un résultat de vérification
        (verification_id), d'une URL externe ou d'un sujet de recherche.
        Utilise les modules de scraping de app.infrastructure sans les modifier.
        """
        title = ""
        summary = ""
        content = ""
        fact_check_claim = None
        rating = None
        image_url = None
        linked_news_id = req.news_id
        linked_verification_id = req.verification_id

        # Cas 1 : Génération depuis une Vérification existante
        if req.verification_id:
            verif_res = await session.execute(
                select(VerificationRequest).where(VerificationRequest.id == req.verification_id)
            )
            verif = verif_res.scalar_one_or_none()
            if not verif:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Vérification source introuvable.",
                )

            fact_check_claim = verif.claim_text
            # Mapper le verdict au rating éditorial
            rating_map = {
                VerificationVerdict.LIKELY_TRUE: EditorialRating.TRUE,
                VerificationVerdict.LIKELY_FALSE: EditorialRating.FALSE,
                VerificationVerdict.MIXED: EditorialRating.MISLEADING,
                VerificationVerdict.INSUFFICIENT_DATA: EditorialRating.UNPROVEN,
                VerificationVerdict.UNVERIFIED: EditorialRating.UNPROVEN,
            }
            rating = rating_map.get(verif.verdict, EditorialRating.UNPROVEN)

            # Sources analysées
            sources_res = await session.execute(
                select(VerificationSource).where(VerificationSource.verification_id == verif.id)
            )
            sources = list(sources_res.scalars().all())

            title = f"Vérification des faits : {verif.claim_text[:80]}"
            summary = (
                f"L'équipe éditoriale a analysé l'affirmation suivante : '{verif.claim_text}'. "
                f"Verdict : {verif.verdict.value} (score de confiance : {int(verif.confidence_score * 100)}%)."
            )

            sources_md = "\n".join(
                [f"- **[{s.title or s.source_type}]({s.url})** : {s.snippet[:150]}..." for s in sources]
            )

            content = (
                f"## Affirmation analysée\n\n> {verif.claim_text}\n\n"
                f"## Résumé de l'enquête\n\n"
                f"{verif.analysis_summary or 'Analyse multi-sources réalisée par notre cellule de fact-checking.'}\n\n"
                f"## Sources et éléments de preuve\n\n"
                f"Au total, {verif.sources_found} source(s) ont été passées au crible :\n"
                f"- Sources concordantes : {verif.sources_supporting}\n"
                f"- Sources contradictoires : {verif.sources_contradicting}\n\n"
                f"{sources_md}\n\n"
                f"## Conclusion éditoriale\n\n"
                f"Au vu des éléments réunis, cette affirmation est qualifiée de **{rating.value.upper()}**."
            )

        # Cas 2 : Génération depuis une News collectée existante
        elif req.news_id:
            news_res = await session.execute(
                select(NewsArticle).where(NewsArticle.id == req.news_id)
            )
            news = news_res.scalar_one_or_none()
            if not news:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Article d'actualité source introuvable.",
                )

            title = f"Décryptage : {news.title}"
            summary = (news.content[:200] + "...") if len(news.content) > 200 else news.content
            image_url = news.image_url
            source_info = f"Source d'origine : [{news.source.value.upper()}]({news.source_url})" if news.source_url else f"Source : {news.source.value}"

            content = (
                f"## Contexte\n\n"
                f"Une publication récente relayée via {news.source.value} a retenu l'attention de notre rédaction.\n\n"
                f"{source_info}\n\n"
                f"## Contenu rapporté\n\n"
                f"{news.content}\n\n"
                f"## Analyse critique\n\n"
                f"*(Complétez ici l'analyse factuelle et la mise en perspective des journalistes)*\n\n"
                f"## Ce qu'il faut retenir\n\n"
                f"- Élément clé 1\n- Élément clé 2"
            )

        # Cas 3 : Scraping d'une URL externe via scraper.py
        elif req.source_url:
            scraped = await scrape_page_content(req.source_url)
            if not scraped:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Impossible de scraper l'URL fournie. Vérifiez l'accessibilité du lien.",
                )

            title = scraped.title or f"Enquête sur l'article du {datetime.now().strftime('%d/%m/%Y')}"
            image_url = scraped.image_url
            summary = scraped.content[:250] + "..." if len(scraped.content) > 250 else scraped.content

            content = (
                f"## Article source\n\n"
                f"Source originale : [{scraped.title or req.source_url}]({req.source_url})\n"
                f"Auteur original : {scraped.author or 'Non spécifié'}\n\n"
                f"## Extrait des faits\n\n"
                f"{scraped.content[:1500]}\n\n"
                f"## Vérification & Angle éditorial\n\n"
                f"*(Insérez ici les contre-vérifications et l'avis de la rédaction)*"
            )

        # Cas 4 : Recherche thématique en direct via search_and_verify
        elif req.topic:
            results = await search_and_verify(req.topic)
            title = f"Enquête éditoriale : {req.topic}"
            summary = f"Dossier thématique et recherche de sources autour de : '{req.topic}'."
            fact_check_claim = req.topic

            sources_snippets = "\n".join(
                [f"- [{r.title}]({r.url}) ({r.source}) : {r.snippet}" for r in results[:5]]
            )

            content = (
                f"## Sujet d'investigation\n\n"
                f"> {req.topic}\n\n"
                f"## Premières sources identifiées sur le web et les réseaux\n\n"
                f"{sources_snippets or 'Aucune source publique directe trouvée.'}\n\n"
                f"## Analyse approfondie de la rédaction\n\n"
                f"*(Rédigez les arguments et témoignages recueillis)*"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Veuillez fournir au moins news_id, verification_id, source_url ou un topic.",
            )

        # Enregistrer l'ébauche générée
        draft_create = EditorialArticleCreate(
            title=title[:500],
            summary=summary,
            content=content,
            fact_check_claim=fact_check_claim,
            editorial_rating=rating,
            category=req.category,
            featured_image_url=image_url,
            linked_news_id=linked_news_id,
            linked_verification_id=linked_verification_id,
            is_featured=False,
        )

        return await EditorialService.create_article(session, draft_create, author)
