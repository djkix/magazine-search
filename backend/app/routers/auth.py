from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.config import get_settings
from app.database import get_db
from app.deps import COOKIE_NAME, get_current_user
from app.models import User
from app.rate_limit import limiter
from app.schemas import LoginRequest, LoginResponse, UserOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter()
settings = get_settings()

# Hash calculé une fois au chargement du module, uniquement pour être vérifié
# quand l'utilisateur n'existe pas. Sans lui, la branche « compte inconnu »
# retourne sans jamais exécuter Argon2, et l'écart de temps de réponse permet
# d'énumérer les comptes existants.
_HASH_FACTICE = hash_password("mot-de-passe-inexistant-pour-egaliser-le-temps")


@router.post("/login", response_model=LoginResponse)
@limiter.limit(settings.login_rate_limit)
def login(request: Request, response: Response, payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        # Même coût de calcul que pour un compte existant, puis même erreur.
        verify_password(payload.password, _HASH_FACTICE)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    user.last_login = func.now()
    db.commit()

    token = create_access_token(subject=user.email, password_hash=user.password_hash)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.jwt_expire_minutes * 60,
    )
    return LoginResponse()


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return {"status": "logged_out"}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
