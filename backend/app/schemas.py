from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models import OcrStatus, PageLanguage, ScanStatus

# ---- Auth ----


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---- Users ----


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    display_name: str
    is_admin: bool
    is_active: bool
    created_at: datetime
    last_login: datetime | None = None


class UserCreate(BaseModel):
    email: EmailStr
    display_name: str
    password: str
    is_admin: bool = False


class UserUpdate(BaseModel):
    display_name: str | None = None
    is_active: bool | None = None
    is_admin: bool | None = None


class PasswordReset(BaseModel):
    new_password: str


# ---- Magazines / Pages ----


class WordBox(BaseModel):
    text: str
    x: float
    y: float
    w: float
    h: float


class PageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    magazine_id: int
    page_number: int
    raw_text: str | None = None
    language: PageLanguage | None = None
    words: list[WordBox] | None = None
    ocr_status: OcrStatus
    error_message: str | None = None


class MagazineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    issue_number: str | None = None
    publication_date: datetime | None = None
    filename: str
    cover_thumbnail_path: str | None = None
    scan_status: ScanStatus
    error_message: str | None = None
    toc_status: OcrStatus
    toc_error_message: str | None = None
    collection_id: int | None = None
    collection_name: str | None = None
    category_id: int | None = None
    category_name: str | None = None
    created_at: datetime
    file_size: int
    page_count: int = 0


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class CategoryCreate(BaseModel):
    name: str


class CategoryUpdate(BaseModel):
    name: str


class CollectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category_id: int | None = None
    category_name: str | None = None


class CollectionSummary(CollectionOut):
    magazine_count: int
    cover_magazine_id: int | None = None


class LibraryOverview(BaseModel):
    collections: list[CollectionSummary]
    unassigned_count: int
    unassigned_cover_magazine_id: int | None = None


class CollectionCreate(BaseModel):
    name: str
    category_id: int | None = None


class CollectionUpdate(BaseModel):
    name: str | None = None
    category_id: int | None = None


class MagazineCollectionUpdate(BaseModel):
    collection_id: int | None
    apply_to_all_issues: bool = False


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    magazine_id: int
    title: str
    start_page: int
    end_page: int | None = None


class ArticleWithMagazine(ArticleOut):
    magazine_title: str
    magazine_issue_number: str | None = None
    category_id: int | None = None
    category_name: str | None = None


class ArticleCreate(BaseModel):
    title: str
    start_page: int
    end_page: int | None = None


class ArticleUpdate(BaseModel):
    title: str | None = None
    start_page: int | None = None
    end_page: int | None = None


# ---- Scan ----


class ScanTriggerResponse(BaseModel):
    job_id: str
    new_files_detected: int


class ScanStatusResponse(BaseModel):
    job_id: str
    detected: int
    processing: int
    done: int
    failed: int
    finished: bool


class RetryFailedResponse(BaseModel):
    retried: int


class LogEntry(BaseModel):
    timestamp: str
    level: str
    logger: str
    message: str
    component: str


class GeminiModelOption(BaseModel):
    id: str
    label: str


class GeminiSettingsResponse(BaseModel):
    model: str
    available_models: list[GeminiModelOption]


class GeminiSettingsUpdate(BaseModel):
    model: str


class AdminStatsResponse(BaseModel):
    total: int
    done: int
    processing: int
    failed: int
    pending: int
    recent: list[MagazineOut]


# ---- Search ----


class SearchHit(BaseModel):
    magazine_id: int
    magazine_title: str
    page_number: int
    page_id: int
    snippet: str
    words: list[WordBox] = []


class SearchResponse(BaseModel):
    query: str
    total_hits: int
    hits: list[SearchHit]
    processing_time_ms: int
