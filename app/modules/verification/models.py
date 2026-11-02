from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLAlchemyEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base


class VerificationStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class VerificationVerdict(str, Enum):
    UNVERIFIED = "unverified"
    LIKELY_TRUE = "likely_true"
    LIKELY_FALSE = "likely_false"
    MIXED = "mixed"
    INSUFFICIENT_DATA = "insufficient_data"


class VerificationRequest(Base):
    __tablename__ = "verification_requests"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    # L'affirmation / information soumise par l'utilisateur
    claim_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Utilisateur qui a soumis la vérification
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[VerificationStatus] = mapped_column(
        SQLAlchemyEnum(
            VerificationStatus,
            name="verification_status",
            native_enum=False,
            create_constraint=True,
        ),
        default=VerificationStatus.PENDING,
        nullable=False,
    )

    verdict: Mapped[VerificationVerdict] = mapped_column(
        SQLAlchemyEnum(
            VerificationVerdict,
            name="verification_verdict",
            native_enum=False,
            create_constraint=True,
        ),
        default=VerificationVerdict.UNVERIFIED,
        nullable=False,
    )

    # Score de confiance (0.0 - 1.0)
    confidence_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    # Résumé de l'analyse
    analysis_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Nombre de sources trouvées
    sources_found: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Sources qui soutiennent l'affirmation
    sources_supporting: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Sources qui contredisent l'affirmation
    sources_contradicting: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relation vers les sources trouvées
    sources = relationship(
        "VerificationSource",
        back_populates="verification",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class VerificationSource(Base):
    __tablename__ = "verification_sources"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    verification_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("verification_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="google",
    )

    url: Mapped[str] = mapped_column(
        String(2000),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    snippet: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    # Le contenu de la source soutient-il l'affirmation ?
    # True = soutient, False = contredit, None = neutre/inconnu
    supports_claim: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        default=None,
    )

    # Score de pertinence (0.0 - 1.0)
    relevance_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relation inverse
    verification = relationship(
        "VerificationRequest",
        back_populates="sources",
    )
