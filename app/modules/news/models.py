from datetime import datetime
from enum import Enum

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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base


class NewsSource(str, Enum):
    FACEBOOK = "facebook"
    GOOGLE = "google"
    WEB = "web"
    MANUAL = "manual"


class NewsStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    FAKE = "fake"
    UNVERIFIED = "unverified"


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    source: Mapped[NewsSource] = mapped_column(
        SQLAlchemyEnum(
            NewsSource,
            name="news_source",
            native_enum=False,
            create_constraint=True,
        ),
        default=NewsSource.WEB,
        nullable=False,
    )

    source_url: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
    )

    author: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    image_url: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
    )

    status: Mapped[NewsStatus] = mapped_column(
        SQLAlchemyEnum(
            NewsStatus,
            name="news_status",
            native_enum=False,
            create_constraint=True,
        ),
        default=NewsStatus.PENDING,
        nullable=False,
    )

    # Utilisateur qui a collecté la news (optionnel)
    collected_by_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
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
