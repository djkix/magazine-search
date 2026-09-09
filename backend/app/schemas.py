from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models import IssueType, OcrStatus, PageLanguage, ScanStatus

# Longueur minimale exigée à la CRÉATION d'un mot de passe. Volontairement
# non appliquée à la connexion : y imposer la règle renverrait un 422 au lieu
# d'un 401 pour un mot de passe trop court, ce qui divulguerait la politique
# et empêcherait les comptes plus anciens de se connecter pour la changer.
MDP_LONGUEUR_MIN = 12
MDP_LONGUEUR_MAX = 128


def _valider_plage_de_pages(modele):
    """Refuse une page de fin antérieure à la page de début.

    Partagé par ArticleCreate et ArticleUpdate. Les deux bornes étant
    facultatives à la mise à jour, le contrôle ne s'applique que lorsque les
    deux valeurs sont fournies.
    """
    debut = modele.start_page
    fin = modele.end_page
    if debut is not None and fin is not None and fin < debut:
        raise ValueError(
            f"end_page ({fin}) ne peut pas être inférieure à start_page ({debut})."
        )
    return modele


# ---- Auth ----


class LoginRequest(BaseModel):
    email: EmailStr
    # Pas de contrainte de longueur ici : voir la note ci-dessus.
    password: str


class LoginResponse(BaseModel):
    """Réponse de /login : le jeton n'est PAS renvoyé dans le corps.

    L'authentification repose entièrement sur le cookie httpOnly posé par la
    réponse. Renvoyer aussi le jeton en clair invitait à le stocker côté
    client (localStorage), où il redevient lisible par n'importe quel script.
    Le frontend ne l'utilisait pas.
    """

    status: str = "authenticated"


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
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=MDP_LONGUEUR_MIN, max_length=MDP_LONGUEUR_MAX)
    is_admin: bool = False


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    is_active: bool | None = None
    is_admin: bool | None = None


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=MDP_LONGUEUR_MIN, max_length=MDP_LONGUEUR_MAX)


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


class MagazineProgressResponse(BaseModel):
    """Progression page par page d'un numéro en cours de traitement.

    `null` une fois le traitement terminé, échoué, ou jamais démarré : la clé
    Redis sous-jacente est effacée dans ces cas.
    """

    current: int
    total: int


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class MagazineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    issue_number: str | None = None
    publication_date: datetime | None = None
    issue_month: str | None = None
    issue_type: IssueType
    filename: str
    cover_thumbnail_path: str | None = None
    scan_status: ScanStatus
    error_message: str | None = None
    toc_status: OcrStatus
    toc_error_message: str | None = None
    collection_id: int | None = None
    collection_name: str | None = None
    tags: list[TagOut] = []
    created_at: datetime
    updated_at: datetime
    file_size: int
    page_count: int = 0
    article_count: int = 0


class TagCreate(BaseModel):
    name: str


class TagUpdate(BaseModel):
    name: str


class CollectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    tags: list[TagOut] = []


class CollectionSummary(CollectionOut):
    magazine_count: int
    cover_magazine_id: int | None = None


class LibraryOverview(BaseModel):
    collections: list[CollectionSummary]
    unassigned_count: int
    unassigned_cover_magazine_id: int | None = None


class CollectionUpdate(BaseModel):
    name: str


class CollectionTagsUpdate(BaseModel):
    # Borne de cardinalité : sans elle, une liste arbitrairement longue est
    # acceptée et part telle quelle dans un IN (...) SQL.
    tag_ids: list[int] = Field(default_factory=list, max_length=200)


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


class ArticleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    start_page: int = Field(ge=1)
    end_page: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _verifier_ordre_des_pages(self) -> "ArticleCreate":
        return _valider_plage_de_pages(self)


class ArticleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    start_page: int | None = Field(default=None, ge=1)
    end_page: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _verifier_ordre_des_pages(self) -> "ArticleUpdate":
        return _valider_plage_de_pages(self)


# ---- Magazine themes ----


class MagazineThemeOut(BaseModel):
    id: int
    name: str
    magazine_count: int


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
    daily_request_limit: int | None
    rpm_limit: int | None
    requests_used_today: int


class GeminiSettingsUpdate(BaseModel):
    model: str
    daily_request_limit: int | None = None
    rpm_limit: int | None = None


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
    occurrence_count: int
    page_number: int
    page_id: int
    snippet: str
    words: list[WordBox] = []
    publication_date: str | None = None
    issue_number: str | None = None


class SearchResponse(BaseModel):
    query: str
    total_hits: int
    hits: list[SearchHit]
    processing_time_ms: int
