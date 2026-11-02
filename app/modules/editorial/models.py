from __future__ import annotations

from datetime import datetime
from enum import Enum

# pyrefly: ignore[missing-import]
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
# pyrefly: ignore[missing-import]
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base


class EditorialStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class EditorialRating(str, Enum):
    TRUE = "true"
    MOSTLY_TRUE = "mostly_true"
    HALF_TRUE = "half_true"
    MISLEADING = "misleading"
    FALSE = "false"
    UNPROVEN = "unproven"
    SATIRE = "satire"


class EditorialCategory(str, Enum):
    POLITICS = "politique"
    HEALTH = "sante"
    ECONOMY = "economie"
    SOCIETY = "societe"
    SCIENCE_TECH = "science_tech"
    ENVIRONMENT = "environnement"
    INTERNATIONAL = "international"
    GENERAL = "general"


class EditorialArticle(Base):
    __tablename__ = "editorial_articles"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(600),
        unique=True,
        index=True,
        nullable=False,
    )

    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    fact_check_claim: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    editorial_rating: Mapped[EditorialRating | None] = mapped_column(
        SQLAlchemyEnum(
            EditorialRating,
            name="editorial_rating",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=True,
    )

    category: Mapped[EditorialCategory] = mapped_column(
        SQLAlchemyEnum(
            EditorialCategory,
            name="editorial_category",
            native_enum=False,
            create_constraint=True,
        ),
        default=EditorialCategory.GENERAL,
        nullable=False,
    )

    tags: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    featured_image_url: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
    )

    status: Mapped[EditorialStatus] = mapped_column(
        SQLAlchemyEnum(
            EditorialStatus,
            name="editorial_status",
            native_enum=False,
            create_constraint=True,
        ),
        default=EditorialStatus.DRAFT,
        nullable=False,
        index=True,
    )

    author_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    reviewer_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    linked_news_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("news_articles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    linked_verification_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("verification_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    review_feedback: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_featured: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    views_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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

    # Relations
    reviews: Mapped[list[EditorialReview]] = relationship(
        "EditorialReview",
        back_populates="article",
        cascade="all, delete-orphan",
        order_by="EditorialReview.created_at.desc()",
        lazy="selectin",
    )


class EditorialReview(Base):
    __tablename__ = "editorial_reviews"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    article_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("editorial_articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    action: Mapped[str] = mapped_column(
        String(50),
        default="comment",
        nullable=False,
    )

    comment: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relations
    article: Mapped[EditorialArticle] = relationship(
        "EditorialArticle",
        back_populates="reviews",
    )
