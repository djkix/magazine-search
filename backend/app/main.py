import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.database import SessionLocal
from app.models import User
from app.rate_limit import limiter
from app.routers import admin, auth, magazines, search
from app.security import hash_password

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")

settings = get_settings()

app = FastAPI(title="Magazine Search API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(search.router, prefix="/api", tags=["search"])
app.include_router(magazines.router, prefix="/api/magazines", tags=["magazines"])


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
        logger.info("Bootstrap admin account created: %s", settings.admin_bootstrap_email)
    finally:
        db.close()


@app.on_event("startup")
def on_startup() -> None:
    # Schema is managed by Alembic migrations, run via entrypoint.sh before the app starts.
    bootstrap_admin()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
