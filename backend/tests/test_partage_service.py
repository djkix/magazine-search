"""Création idempotente du jeton de partage, factorisée entre l'article et
le numéro entier. Les deux routeurs (articles.py, magazines.py) ne testent
plus que leur propre endpoint HTTP ; ce fichier couvre le cœur partagé
directement, sans passer par une requête."""

import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Article, Magazine
from app.services.partage import obtenir_ou_creer_token_partage


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_genere_un_token_pour_un_article(db_session):
    magazine = Magazine(
        title="Test",
        filename="t.pdf",
        file_path="t.pdf",
        file_hash="h1",
        file_size=1,
        file_mtime=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(magazine)
    db_session.commit()
    article = Article(magazine_id=magazine.id, title="Un article", start_page=1)
    db_session.add(article)
    db_session.commit()

    token = obtenir_ou_creer_token_partage(db_session, Article, article)

    assert len(token) > 20
    assert article.share_token == token


def test_idempotent(db_session):
    magazine = Magazine(
        title="Test",
        filename="t.pdf",
        file_path="t.pdf",
        file_hash="h1",
        file_size=1,
        file_mtime=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(magazine)
    db_session.commit()

    premier = obtenir_ou_creer_token_partage(db_session, Magazine, magazine)
    second = obtenir_ou_creer_token_partage(db_session, Magazine, magazine)

    assert premier == second


def test_course_entre_deux_appels_concurrents(db_session, monkeypatch):
    """Simule une course : share_token est posé par une autre requête juste
    avant que celle-ci ne commite le sien. La mise à jour conditionnelle
    (WHERE share_token IS NULL) doit empêcher l'écrasement, et l'appelant
    doit recevoir le token réellement enregistré, jamais celui qu'il avait
    généré localement avant de perdre la course."""
    import app.services.partage as partage_module

    magazine = Magazine(
        title="Test",
        filename="t.pdf",
        file_path="t.pdf",
        file_hash="h1",
        file_size=1,
        file_mtime=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(magazine)
    db_session.commit()

    token_gagnant = "token-gagnant-de-la-course"

    def faux_token_urlsafe(n):
        # Au moment ou CE thread genere son jeton, un autre a deja gagne et
        # pose le sien directement en base - on le simule ici.
        db_session.query(Magazine).filter(Magazine.id == magazine.id).update({"share_token": token_gagnant})
        db_session.commit()
        return "token-perdant-genere-en-parallele"

    monkeypatch.setattr(partage_module.secrets, "token_urlsafe", faux_token_urlsafe)

    token = obtenir_ou_creer_token_partage(db_session, Magazine, magazine)

    assert token == token_gagnant
