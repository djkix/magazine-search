import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class ScanStatus(str, enum.Enum):
    detected = "detected"
    stable = "stable"
    queued = "queued"
    processing = "processing"
    done = "done"
    failed = "failed"


class IssueType(str, enum.Enum):
    normal = "normal"
    hs = "hs"
    sp = "sp"


class OcrStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    done = "done"
    failed = "failed"


class PageLanguage(str, enum.Enum):
    fr = "fr"
    en = "en"
    mixed = "mixed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Magazine(Base):
    __tablename__ = "magazines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    issue_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    publication_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_mtime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cover_thumbnail_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    scan_status: Mapped[ScanStatus] = mapped_column(
        Enum(ScanStatus, name="scan_status"), default=ScanStatus.detected, nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Unlike created_at (set once, at first scan), this refreshes on every
    # row change - e.g. a reprocess/re-queue - so admin views can tell
    # recent activity apart from when the magazine was first discovered.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    toc_status: Mapped[OcrStatus] = mapped_column(
        Enum(OcrStatus, name="toc_status"), default=OcrStatus.pending, nullable=False
    )
    toc_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Set once a Gemini theme-batch has actually considered this magazine,
    # whether or not it came out of it with any theme - without this, a
    # magazine Gemini couldn't find a theme for (e.g. too few articles) has
    # no way to tell "not tried yet" from "tried, found nothing", so it kept
    # being resubmitted - and re-billed against the daily quota - every time
    # any other magazine's OCR completed and re-enqueued the batch job.
    themed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    issue_type: Mapped[IssueType] = mapped_column(
        Enum(IssueType, name="issue_type"), default=IssueType.normal, nullable=False
    )
    issue_month_label: Mapped[str | None] = mapped_column(String(50), nullable=True)

    collection_id: Mapped[int | None] = mapped_column(
        ForeignKey("collections.id", ondelete="SET NULL"), nullable=True
    )

    pages: Mapped[list["Page"]] = relationship(
        "Page", back_populates="magazine", cascade="all, delete-orphan", order_by="Page.page_number"
    )
    articles: Mapped[list["Article"]] = relationship(
        "Article", back_populates="magazine", cascade="all, delete-orphan", order_by="Article.start_page"
    )
    collection: Mapped[Optional["Collection"]] = relationship("Collection", back_populates="magazines")
    themes: Mapped[list["Theme"]] = relationship("Theme", secondary="theme_magazines", back_populates="magazines")


class Page(Base):
    __tablename__ = "pages"
    __table_args__ = (UniqueConstraint("magazine_id", "page_number", name="uq_page_magazine_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    magazine_id: Mapped[int] = mapped_column(ForeignKey("magazines.id", ondelete="CASCADE"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[PageLanguage | None] = mapped_column(Enum(PageLanguage, name="page_language"), nullable=True)
    # Word-level bounding boxes: [{"text": str, "x": float, "y": float, "w": float, "h": float}, ...]
    # Stored inline per page (JSON) rather than a dedicated Words table, per cahier des charges section 4:
    # simpler at this volume, revisit only if per-page word counts prove a real perf issue.
    words: Mapped[list | None] = mapped_column(JSON, nullable=True)
    ocr_status: Mapped[OcrStatus] = mapped_column(
        Enum(OcrStatus, name="ocr_status"), default=OcrStatus.pending, nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    magazine: Mapped["Magazine"] = relationship("Magazine", back_populates="pages")


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    magazine_id: Mapped[int] = mapped_column(ForeignKey("magazines.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    start_page: Mapped[int] = mapped_column(Integer, nullable=False)
    end_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    magazine: Mapped["Magazine"] = relationship("Magazine", back_populates="articles")


collection_tags = Table(
    "collection_tags",
    Base.metadata,
    Column("collection_id", ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Tag(Base):
    """Admin-defined theme (e.g. "Bricolage", "Guide achat") that groups one or
    more Collections (many-to-many). Search and library filtering scope to a
    Tag, which transparently covers every magazine in every Collection
    tagged with it."""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    collections: Mapped[list["Collection"]] = relationship(
        "Collection", secondary=collection_tags, back_populates="tags"
    )


class Collection(Base):
    """A magazine title/publication (e.g. "Que Choisir"), grouping every issue
    published under that title. Can carry multiple Tags."""

    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tags: Mapped[list["Tag"]] = relationship("Tag", secondary=collection_tags, back_populates="collections")
    magazines: Mapped[list["Magazine"]] = relationship("Magazine", back_populates="collection")


theme_magazines = Table(
    "theme_magazines",
    Base.metadata,
    Column("theme_id", ForeignKey("themes.id", ondelete="CASCADE"), primary_key=True),
    Column("magazine_id", ForeignKey("magazines.id", ondelete="CASCADE"), primary_key=True),
)


class Theme(Base):
    """A Gemini-generated topic (e.g. "Automobile", "Santé"), assigned to a
    magazine once at indexing time from its extracted sommaire. The name
    vocabulary is shared across the whole library - a magazine being
    processed is shown the themes already in use so Gemini reuses a
    matching one instead of inventing a near-duplicate (e.g. "Voitures" vs
    "Automobile")."""

    __tablename__ = "themes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    magazines: Mapped[list["Magazine"]] = relationship(
        "Magazine", secondary=theme_magazines, back_populates="themes"
    )


class Setting(Base):
    """Generic key/value store for admin-editable settings that should take
    effect without a redeploy (e.g. which Gemini model to use)."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
