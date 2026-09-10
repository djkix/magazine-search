import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.database import SessionLocal
from app.logging_config import configure_logging
from app.models import User
from app.rate_limit import limiter
from app.routers import admin, articles, auth, collections, magazines, search, tags, themes
from app.security import hash_password

configure_logging("backend")
logger = logging.getLogger("app")

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Le schéma est géré par les migrations Alembic, lancées par entrypoint.sh
    # avant le démarrage de l'application.
    bootstrap_admin()
    yield


app = FastAPI(
    title="Magazine Search API",
    lifespan=lifespan,
    # Fermés par défaut : /docs et /openapi.json cartographient toute la
    # surface d'API pour qui sait où regarder. À activer via ENABLE_API_DOCS
    # en développement local uniquement.
    docs_url="/api/docs" if settings.enable_api_docs else None,
    redoc_url="/api/redoc" if settings.enable_api_docs else None,
    openapi_url="/api/openapi.json" if settings.enable_api_docs else None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Pas de repli sur ["*"] : combiné à allow_credentials=True, Starlette
# renvoie l'origine du demandeur quelle qu'elle soit, ce qui laisse n'importe
# quel site appeler l'API avec le cookie de session de l'utilisateur. Si
# BACKEND_CORS_ORIGINS n'est pas renseigné, aucune origine tierce n'est
# autorisée — ce qui est le fonctionnement normal ici, puisque le frontend
# relaie /api/* sur sa propre origine et n'a donc pas besoin de CORS.
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(search.router, prefix="/api", tags=["search"])
app.include_router(magazines.router, prefix="/api/magazines", tags=["magazines"])
app.include_router(articles.router, prefix="/api/articles", tags=["articles"])
app.include_router(tags.router, prefix="/api/tags", tags=["tags"])
app.include_router(collections.router, prefix="/api/collections", tags=["collections"])
app.include_router(themes.router, prefix="/api/themes", tags=["themes"])


def bootstrap_admin() -> None:
    if not settings.admin_bootstrap_email or not settings.admin_bootstrap_password:
        return
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.is_admin.is_(True)).first()
        if existing:
            return
        admin_user = User(
            email=settings.admin_bootstrap_email,
            password_hash=hash_password(settings.admin_bootstrap_password),
            display_name="Admin",
            is_admin=True,
            is_active=True,
        )
        db.add(admin_user)
        db.commit()
        # L'adresse n'est pas journalisée : les logs applicatifs sont
        # consultables depuis le backoffice, inutile d'y exposer l'identifiant
        # du compte administrateur.
        logger.info("Compte administrateur d'amorçage créé")
    finally:
        db.close()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
