import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
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

    toc_status: Mapped[OcrStatus] = mapped_column(
        Enum(OcrStatus, name="toc_status"), default=OcrStatus.pending, nullable=False
    )
    toc_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

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


class Category(Base):
    """Admin-defined theme (e.g. "Bricolage", "Guide achat") that groups one or
    more Collections. Search and library filtering scope to a Category, which
    transparently covers every magazine in every Collection it contains."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    collections: Mapped[list["Collection"]] = relationship("Collection", back_populates="category")


class Collection(Base):
    """A magazine title/publication (e.g. "Que Choisir"), grouping every issue
    published under that title. Belongs to one Category."""

    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    category: Mapped[Optional["Category"]] = relationship("Category", back_populates="collections")
    magazines: Mapped[list["Magazine"]] = relationship("Magazine", back_populates="collection")


class Setting(Base):
    """Generic key/value store for admin-editable settings that should take
    effect without a redeploy (e.g. which Gemini model to use)."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
