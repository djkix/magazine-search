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
    created_at: datetime
    file_size: int
    page_count: int = 0


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
