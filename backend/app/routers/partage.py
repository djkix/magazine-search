from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Article, Magazine
from app.schemas import PartageOut
from app.services.pdf_streaming import CACHE_PDF, resoudre_chemin_pdf, servir_pdf

# Delibere : AUCUNE Depends(get_current_user) sur ce routeur. C'est le seul
# point d'entree de l'application accessible sans session — tout son interet
# est la : un lien envoye par un canal prive (WhatsApp) doit s'ouvrir sans
# qu'on demande un compte a la personne qui le recoit.
router = APIRouter()


def _get_article_ou_404(token: str, db: Session) -> Article:
    # Jointure explicite plutot que le lazy-loading par defaut : sans elle,
    # chaque appel sur cet endpoint PUBLIC (potentiellement a fort trafic,
    # un lien WhatsApp pouvant etre ouvert par plusieurs personnes) faisait
    # 3 aller-retours DB sequentiels (article, puis magazine, puis
    # collection) au lieu d'un seul.
    article = (
        db.query(Article)
        .options(joinedload(Article.magazine).joinedload(Magazine.collection))
        .filter(Article.share_token == token)
        .first()
    )
    if not article:
        # 404 generique, indiscernable d'un token qui n'a jamais existe : ne
        # pas confirmer a un tiers qu'un token "presque bon" existe.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lien introuvable.")
    return article


@router.get("/{token}", response_model=PartageOut)
def partage_metadonnees(token: str, db: Session = Depends(get_db)):
    article = _get_article_ou_404(token, db)
    magazine = article.magazine
    return PartageOut(
        article_title=article.title,
        magazine_title=magazine.title,
        collection_name=magazine.collection.name if magazine.collection else None,
        start_page=article.start_page,
        end_page=article.end_page,
    )


@router.get("/{token}/file")
def partage_fichier(token: str, requete: Request, db: Session = Depends(get_db)):
    article = _get_article_ou_404(token, db)
    magazine = article.magazine
    pdf_path = resoudre_chemin_pdf(magazine)
    if not pdf_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF file not available")
    return servir_pdf(pdf_path, magazine.filename, "inline", requete, CACHE_PDF)
