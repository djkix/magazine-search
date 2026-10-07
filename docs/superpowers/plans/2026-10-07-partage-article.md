# Partage d'un article par lien — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permettre de partager un article précis d'un numéro via un lien public, sans compte, qui streame le magazine par plages HTTP (jamais un téléchargement complet) et reste valide indéfiniment.

**Architecture:** Un token aléatoire (`share_token`) ajouté à `Article`, résolu par un nouveau routeur FastAPI public (sans dépendance d'authentification) qui réutilise le service de streaming PDF existant. Côté frontend, une page hors du groupe authentifié affiche l'article via le même composant `PdfViewer` que le lecteur normal, avec le pré-chargement de fond désactivé.

**Tech Stack:** FastAPI + SQLAlchemy + Alembic (backend), Next.js 14 App Router + pdf.js via `PdfViewer.tsx` (frontend). Aucune nouvelle dépendance.

**Spec:** `docs/superpowers/specs/2026-10-07-partage-article-design.md`

## Global Constraints

- L'unité partagée est l'**article**, jamais le numéro entier.
- Lecture publique **sans aucune authentification** — pas de cookie de session, pas de redirection vers `/login`.
- **Pas d'expiration, pas de révocation.** Pas de table séparée : un seul champ nullable sur `Article`.
- Le lien sert le **magazine entier par streaming** (plages HTTP), jamais un fichier découpé par article.
- Bouton "Partager" dans les listes d'articles existantes (panneau du lecteur + page "Sommaires" d'une collection) — pas dans la visionneuse elle-même.
- Token inconnu → 404 générique, indiscernable d'un token qui n'a jamais existé.
- Commits groupés : ce plan ne commit JAMAIS automatiquement au nom de l'utilisateur. Chaque étape "Commit" ci-dessous crée un commit local normal (`git commit`), mais **aucun `git push` n'est fait par ce plan** — c'est une règle du projet, pas de ce plan, et elle s'applique en dehors de l'exécution de ce plan aussi.

## Review Focus

- **Lien de partage ouvert par un utilisateur déjà connecté** : il doit voir l'article normalement, pas être éjecté vers `/`. Le middleware ne doit traiter `/partage/*` que comme "public", jamais comme "redirige si authentifié" (ce dernier comportement est réservé à `/login`).
- **Token syntaxiquement plausible mais inexistant** (ex. une chaîne de la bonne longueur mais jamais générée) : 404, pas une erreur 500 (une requête SQLAlchemy mal formée sur un filtre `==` ne doit pas planter).
- **Article dont le numéro n'a pas de fichier PDF accessible** (NAS démonté, fichier déplacé) : 404 clair sur `/partage/{token}/file`, pas une 500 qui fuiterait un chemin de fichier serveur dans la réponse.
- **En-tête `Range` malformé ou absent sur `/partage/{token}/file`** : doit se comporter exactement comme `/magazines/{id}/file` aujourd'hui (repli sur la réponse complète), pas différemment parce que c'est un nouvel appelant.
- **Deux clics successifs sur "Partager" pour le même article** : doivent renvoyer le même lien, pas deux liens différents qui cohabiteraient (un seul token valide par article, jamais une liste qui grossit).

---

## Task 1: Extraire le streaming PDF en service partagé

Le code qui sert un PDF par plages HTTP (gestion de l'en-tête `Range`, 206/416, `Accept-Ranges`) vit aujourd'hui entièrement dans `magazines.py`, sous des noms préfixés `_` (privés au module). Le nouveau routeur public de partage (Task 4) doit l'utiliser aussi — on l'extrait d'abord dans un service partagé, sans rien changer à son comportement. Ce service n'a par ailleurs **aucun test automatisé aujourd'hui** (seulement vérifié manuellement en session précédente) : cette tâche comble ce manque au passage.

**Files:**
- Create: `backend/app/services/pdf_streaming.py`
- Modify: `backend/app/routers/magazines.py:1-16` (imports), `:186-290` (suppression du code déplacé), `:309-324` (adaptation des deux appelants)
- Test: `backend/tests/test_pdf_streaming.py`

**Interfaces:**
- Produces: `app.services.pdf_streaming.servir_pdf(chemin: Path, nom: str, disposition: str, requete: Request, cache: str | None) -> Response` ; `app.services.pdf_streaming.resoudre_chemin_pdf(magazine: Magazine) -> Path` ; `app.services.pdf_streaming.CACHE_PDF: str`

- [ ] **Step 1: Write the failing test**

Créer `backend/tests/test_pdf_streaming.py` :

```python
"""Service de streaming PDF par plages HTTP.

Aucun appel réseau, aucune base : seule la fonction `servir_pdf` est
appelée, sur un petit fichier créé pour le test. Ce service n'avait aucune
couverture automatisée avant ce test — seulement vérifié manuellement lors
de son introduction.
"""

import asyncio

import pytest
from starlette.datastructures import Headers

from app.services.pdf_streaming import servir_pdf


class FakeRequest:
    def __init__(self, range_header: str | None):
        self.headers = Headers({"range": range_header} if range_header else {})


async def _lire_corps(reponse) -> bytes:
    if not hasattr(reponse, "body_iterator"):
        return reponse.body
    corps = b""
    async for morceau in reponse.body_iterator:
        corps += morceau if isinstance(morceau, bytes) else morceau.encode()
    return corps


@pytest.fixture
def fichier(tmp_path):
    chemin = tmp_path / "test.pdf"
    chemin.write_bytes(b"%PDF-1.4\n" + b"A" * 991)  # 1000 octets
    return chemin


def test_sans_en_tete_range_sert_tout(fichier):
    reponse = servir_pdf(fichier, "test.pdf", "inline", FakeRequest(None), "private, max-age=3600")
    assert reponse.status_code == 200
    assert reponse.headers["accept-ranges"] == "bytes"


def test_plage_normale(fichier):
    reponse = servir_pdf(fichier, "test.pdf", "inline", FakeRequest("bytes=0-9"), None)
    assert reponse.status_code == 206
    assert reponse.headers["content-range"] == "bytes 0-9/1000"
    corps = asyncio.run(_lire_corps(reponse))
    assert corps == b"%PDF-1.4\nA"


def test_plage_suffixe(fichier):
    reponse = servir_pdf(fichier, "test.pdf", "inline", FakeRequest("bytes=-10"), None)
    assert reponse.status_code == 206
    assert reponse.headers["content-range"] == "bytes 990-999/1000"
    corps = asyncio.run(_lire_corps(reponse))
    assert corps == b"A" * 10


def test_plage_hors_limites_renvoie_416(fichier):
    reponse = servir_pdf(fichier, "test.pdf", "inline", FakeRequest("bytes=5000-6000"), None)
    assert reponse.status_code == 416
    assert reponse.headers["content-range"] == "bytes */1000"


def test_en_tete_illisible_sert_tout(fichier):
    reponse = servir_pdf(fichier, "test.pdf", "inline", FakeRequest("n-importe-quoi"), None)
    assert reponse.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_pdf_streaming.py -v`
Expected: FAIL avec `ModuleNotFoundError: No module named 'app.services.pdf_streaming'`

- [ ] **Step 3: Créer le service, en déplaçant le code existant**

Créer `backend/app/services/pdf_streaming.py` avec exactement le contenu actuellement privé dans `magazines.py` (lignes 196-290), renommé sans underscore pour les deux symboles désormais publics :

```python
import re
from collections.abc import Iterator
from pathlib import Path

from fastapi import Request, Response, status
from fastapi.responses import FileResponse, StreamingResponse

from app.models import Magazine


def resoudre_chemin_pdf(magazine: Magazine) -> Path:
    from app.config import get_settings

    settings = get_settings()
    processed_path = Path(settings.processed_dir) / f"{magazine.id}.pdf"
    if processed_path.exists():
        return processed_path
    return Path(settings.nas_mount_path) / magazine.file_path


# Le PDF est lourd et relu page apres page : le garder une heure evite de le
# retelecharger a chaque reouverture du lecteur. Duree courte car un
# retraitement OCR le remplace au meme emplacement.
CACHE_PDF = "private, max-age=3600"

# Starlette 0.38 ne gere pas l'en-tete Range sur FileResponse (verifie sur
# l'image deployee). Consequence : chaque ouverture du lecteur telechargeait
# le PDF entier — 36 Mo pour un Computer Music — pour afficher une seule page,
# et arriver page 87 depuis un resultat de recherche imposait de rapatrier
# tout le reste. pdf.js sait ne demander que les octets utiles, mais seulement
# si le serveur annonce « Accept-Ranges ».
#
# On ne traite qu'UNE plage par requete. C'est ce qu'emet pdf.js, et repondre
# au cas general (plages multiples en multipart/byteranges) couterait bien
# plus a ecrire et a maintenir que ce que ca rapporterait ici.
_PLAGE_RE = re.compile(r"^bytes=(?P<debut>\d*)-(?P<fin>\d*)$")

# 64 Kio : assez grand pour ne pas multiplier les allers-retours disque, assez
# petit pour ne pas charger une plage entiere en memoire quand pdf.js en
# demande une grosse.
TAILLE_MORCEAU = 64 * 1024


def _lire_plage(chemin: Path, debut: int, longueur: int) -> Iterator[bytes]:
    """Rend le contenu du fichier par morceaux, sans le charger en entier."""
    with chemin.open("rb") as fichier:
        fichier.seek(debut)
        restant = longueur
        while restant > 0:
            morceau = fichier.read(min(TAILLE_MORCEAU, restant))
            if not morceau:
                break
            restant -= len(morceau)
            yield morceau


def servir_pdf(chemin: Path, nom: str, disposition: str, requete: Request, cache: str | None):
    """Sert un PDF en honorant l'en-tete Range quand le client en envoie un.

    Sans en-tete Range, ou avec un en-tete qu'on ne sait pas lire, on retombe
    sur la reponse complete habituelle — mais en annoncant « Accept-Ranges »,
    sans quoi le client ne tenterait jamais de requete partielle.

    Partage par `/magazines/{id}/file`, `/magazines/{id}/download` et
    `/partage/{token}/file` : le comportement est identique quel que soit
    l'appelant, authentifie ou public — seule la resolution du chemin et
    l'autorisation d'y acceder different en amont.
    """
    taille = chemin.stat().st_size
    entetes = {"Accept-Ranges": "bytes"}
    if cache:
        entetes["Cache-Control"] = cache

    brut = requete.headers.get("range")
    correspondance = _PLAGE_RE.match(brut.strip()) if brut else None
    if correspondance is None:
        return FileResponse(
            chemin,
            media_type="application/pdf",
            filename=nom,
            content_disposition_type=disposition,
            headers=entetes,
        )

    debut_txt, fin_txt = correspondance.group("debut"), correspondance.group("fin")
    if not debut_txt and not fin_txt:
        # « bytes=- » ne designe rien : on sert tout plutot que d'echouer.
        return FileResponse(
            chemin,
            media_type="application/pdf",
            filename=nom,
            content_disposition_type=disposition,
            headers=entetes,
        )

    if not debut_txt:
        # Forme suffixe « bytes=-500 » : les 500 derniers octets.
        longueur = min(int(fin_txt), taille)
        debut, fin = taille - longueur, taille - 1
    else:
        debut = int(debut_txt)
        fin = min(int(fin_txt), taille - 1) if fin_txt else taille - 1

    if debut >= taille or debut > fin:
        # 416 obligatoire : renvoyer 200 ferait croire au client que sa plage
        # a ete servie, et pdf.js interpreterait le fichier de travers.
        return Response(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            headers={**entetes, "Content-Range": f"bytes */{taille}"},
        )

    longueur = fin - debut + 1
    return StreamingResponse(
        _lire_plage(chemin, debut, longueur),
        status_code=status.HTTP_206_PARTIAL_CONTENT,
        media_type="application/pdf",
        headers={
            **entetes,
            "Content-Range": f"bytes {debut}-{fin}/{taille}",
            "Content-Length": str(longueur),
            "Content-Disposition": f'{disposition}; filename="{nom}"',
        },
    )
```

Note : `resoudre_chemin_pdf` importe `get_settings` à l'intérieur de la fonction (pas en tête de module) pour éviter tout risque de cycle d'import entre `app.config` et `app.services.pdf_streaming` — vérifier à l'implémentation si un import en tête de fichier fonctionne aussi (probablement oui, `app/config.py` n'importe aucun service) ; si c'est le cas, le remonter en tête de fichier est plus propre et doit être préféré.

Puis modifier `backend/app/routers/magazines.py` :
- Retirer les imports devenus inutiles : `re`, `Iterator` (de `collections.abc`), `StreamingResponse`, `Response` (de `fastapi`).
- Retirer `_resolve_pdf_path`, `CACHE_PDF`, `_PLAGE_RE`, `TAILLE_MORCEAU`, `_lire_plage`, `_servir_pdf` (tout le bloc).
- Ajouter : `from app.services.pdf_streaming import CACHE_PDF, resoudre_chemin_pdf, servir_pdf`.
- Dans `view_file` et `download_file`, remplacer `_resolve_pdf_path(magazine)` par `resoudre_chemin_pdf(magazine)` et `_servir_pdf(...)` par `servir_pdf(...)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_pdf_streaming.py -v`
Expected: 5 passed

- [ ] **Step 5: Vérifier que rien d'autre n'a cassé**

Run (depuis `backend/`, avec le venv du projet activé et les variables d'environnement de test posées) :
```bash
python3 -c "import app.main; print('import OK')"
pytest -q
```
Expected: `import OK`, suite complète verte (aucune régression sur `magazines.py`).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/pdf_streaming.py backend/app/routers/magazines.py backend/tests/test_pdf_streaming.py
git commit -m "refactor(pdf): extraire le streaming par plages en service partagé

Le partage d'article (à venir) doit réutiliser ce code sans piocher dans
des noms privés d'un autre routeur. Comble au passage l'absence de test
automatisé sur ce service — seulement vérifié manuellement jusqu'ici.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 2: Colonne `share_token` sur Article

**Files:**
- Create: `backend/alembic/versions/0017_article_share_token.py`
- Modify: `backend/app/models.py` (classe `Article`, après `end_page`)

**Interfaces:**
- Produces: `Article.share_token: str | None` (colonne, nullable, unique, indexée)

- [ ] **Step 1: Ajouter la colonne au modèle**

Dans `backend/app/models.py`, classe `Article` (vérifier d'abord le nom de la dernière révision Alembic réellement présente dans `backend/alembic/versions/` à ce moment — ce plan a été écrit avec `0016_google_sub.py` comme dernière révision ; si une autre a été ajoutée depuis, le `down_revision` ci-dessous doit pointer vers celle-là, pas vers `"0016"` en dur) :

```python
    end_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Jeton de partage public : nul tant que l'article n'a jamais été
    # partagé, genere a la demande au premier clic sur "Partager". Pas de
    # table separee : sans expiration ni revocation, il n'y a rien de plus
    # a tracer qu'un champ sur la ligne existante.
    share_token: Mapped[str | None] = mapped_column(String(43), unique=True, index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

(`String` est déjà importé dans ce fichier — vérifier avant d'ajouter l'import.)

- [ ] **Step 2: Écrire la migration**

Créer `backend/alembic/versions/0017_article_share_token.py` :

```python
"""ajouter share_token aux articles pour le partage par lien

Permet de partager un article precis via un lien public, sans compte :
voir docs/superpowers/specs/2026-10-07-partage-article-design.md. La
colonne est nullable (la quasi-totalite des articles ne sont jamais
partages) et generee a la demande, pas a l'extraction du sommaire.

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("share_token", sa.String(length=43), nullable=True))
    op.create_index("ix_articles_share_token", "articles", ["share_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_articles_share_token", table_name="articles")
    op.drop_column("articles", "share_token")
```

- [ ] **Step 3: Vérifier la migration en mode génération SQL** (pas de Postgres réel dans cet environnement)

Run (depuis `backend/`) :
```bash
DATABASE_URL="postgresql+psycopg://fake:fake@localhost/fake" alembic upgrade head --sql | tail -10
DATABASE_URL="postgresql+psycopg://fake:fake@localhost/fake" alembic downgrade 0017:0016 --sql | tail -10
```
Expected : la montée affiche `ALTER TABLE articles ADD COLUMN share_token VARCHAR(43);` puis `CREATE UNIQUE INDEX ix_articles_share_token ON articles (share_token);` ; la descente affiche les deux instructions inverses dans l'ordre inverse.

- [ ] **Step 4: Vérifier l'import de l'application**

Run : `python3 -c "import app.main; print('import OK')"`
Expected: `import OK`

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/0017_article_share_token.py backend/app/models.py
git commit -m "feat(partage): ajouter share_token aux articles

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 3: Endpoint authentifié de création du partage

**Files:**
- Modify: `backend/app/schemas.py` (ajouter `ArticleShareOut`)
- Modify: `backend/app/routers/articles.py` (ajouter `POST /{article_id}/share`)
- Test: `backend/tests/test_partage.py` (nouveau fichier)

**Interfaces:**
- Consumes: `Article.share_token` (Task 2)
- Produces: `POST /api/articles/{article_id}/share` → `{"token": str}`, idempotent

- [ ] **Step 1: Write the failing test**

Créer `backend/tests/test_partage.py` :

```python
"""Partage d'un article par lien public, sans compte.

Vérifie trois choses : la création du token est idempotente (section 2 de
la conception), et les routes publiques (ajoutées en Task 4) ne dépendent
d'aucune session — elles ne sont pas encore testées ici, seule la création
authentifiée l'est dans cette première tâche.
"""

import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.deps import get_current_user
from app.main import app
from app.models import Article, Magazine, User


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


@pytest.fixture
def client(db_session):
    def _get_db():
        yield db_session

    def _utilisateur():
        u = User()
        u.id = 1
        u.email = "utilisateur@exemple.fr"
        u.display_name = "Utilisateur"
        u.is_admin = False
        u.is_active = True
        u.password_hash = "hash-non-utilise-ici"
        return u

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _utilisateur
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def article(db_session):
    magazine = Magazine(
        title="Test",
        filename="test.pdf",
        file_path="test.pdf",
        file_hash="h1",
        file_size=1000,
        file_mtime=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(magazine)
    db_session.commit()
    a = Article(magazine_id=magazine.id, title="Un article", start_page=5, end_page=7)
    db_session.add(a)
    db_session.commit()
    return a


def test_creation_du_partage_genere_un_token(client, article):
    reponse = client.post(f"/api/articles/{article.id}/share")

    assert reponse.status_code == 200
    assert len(reponse.json()["token"]) > 20


def test_deux_appels_renvoient_le_meme_token(client, article):
    premier = client.post(f"/api/articles/{article.id}/share").json()["token"]
    second = client.post(f"/api/articles/{article.id}/share").json()["token"]

    assert premier == second


def test_article_inconnu_404(client):
    reponse = client.post("/api/articles/999999/share")

    assert reponse.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_partage.py -v`
Expected: FAIL (404 ou erreur de méthode — la route `POST /{article_id}/share` n'existe pas encore)

- [ ] **Step 3: Write minimal implementation**

Dans `backend/app/schemas.py`, à côté des autres schémas liés aux articles :

```python
class ArticleShareOut(BaseModel):
    token: str
```

Dans `backend/app/routers/articles.py`, ajouter les imports nécessaires et la route :

```python
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Article, Collection, Magazine
from app.schemas import ArticleShareOut, ArticleWithMagazine
```

(`HTTPException`, `status`, `secrets` s'ajoutent aux imports existants de ce fichier.)

```python
# 32 octets -> 43 caracteres en base64 URL-safe : meme generation que pour
# les secrets applicatifs (voir google_auth.py), largement hors de portee
# d'une attaque par force brute sur l'URL.
TAILLE_TOKEN_OCTETS = 32


@router.post("/{article_id}/share", response_model=ArticleShareOut)
def share_article(article_id: int, db: Session = Depends(get_db)):
    """Cree ou retrouve le lien de partage public d'un article.

    Idempotent : rejouer l'appel sur un article deja partage renvoie le
    meme token plutot que d'en generer un second — un seul lien valide par
    article, jamais une liste qui grossit a chaque clic.
    """
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")

    if not article.share_token:
        article.share_token = secrets.token_urlsafe(TAILLE_TOKEN_OCTETS)
        db.commit()

    return ArticleShareOut(token=article.share_token)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_partage.py -v`
Expected: 3 passed

- [ ] **Step 5: Vérifier l'ensemble de la suite**

Run: `pytest -q` (depuis `backend/`)
Expected: suite complète verte, aucune régression.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas.py backend/app/routers/articles.py backend/tests/test_partage.py
git commit -m "feat(partage): endpoint authentifié de création du lien de partage

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 4: Routeur public de consultation (métadonnées + fichier)

**Files:**
- Create: `backend/app/routers/partage.py`
- Modify: `backend/app/schemas.py` (ajouter `PartageOut`)
- Modify: `backend/app/main.py` (enregistrer le routeur)
- Test: `backend/tests/test_partage.py` (étendre)

**Interfaces:**
- Consumes: `Article.share_token` (Task 2), `app.services.pdf_streaming.servir_pdf`/`resoudre_chemin_pdf`/`CACHE_PDF` (Task 1)
- Produces: `GET /api/partage/{token}` → `PartageOut` ; `GET /api/partage/{token}/file` → PDF par plages, SANS authentification

- [ ] **Step 1: Write the failing test**

Ajouter à `backend/tests/test_partage.py` (les fixtures `db_session`, `client`, `article` existent déjà depuis la Task 3) :

```python
def test_metadonnees_token_inconnu_404(client):
    reponse = client.get("/api/partage/un-token-qui-n-existe-pas")

    assert reponse.status_code == 404


def test_metadonnees_token_valide(client, article):
    token = client.post(f"/api/articles/{article.id}/share").json()["token"]

    reponse = client.get(f"/api/partage/{token}")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["article_title"] == "Un article"
    assert corps["magazine_title"] == "Test"
    assert corps["start_page"] == 5
    assert corps["end_page"] == 7


def test_metadonnees_accessible_sans_authentification(client, article):
    """Preuve que la route est reellement publique : aucun override de
    get_current_user n'est pose, contrairement au fixture `client` pour les
    autres tests de ce fichier — si la route exigeait une session, elle
    echouerait ici avec 401 plutot que de repondre normalement."""
    token = client.post(f"/api/articles/{article.id}/share").json()["token"]
    app.dependency_overrides.pop(get_current_user, None)

    reponse = client.get(f"/api/partage/{token}")

    assert reponse.status_code == 200


def test_fichier_sert_le_pdf_par_plages(client, article, db_session, tmp_path, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "processed_dir", str(tmp_path))
    (tmp_path / f"{article.magazine_id}.pdf").write_bytes(b"%PDF-1.4\n" + b"A" * 991)

    token = client.post(f"/api/articles/{article.id}/share").json()["token"]
    app.dependency_overrides.pop(get_current_user, None)

    reponse = client.get(f"/api/partage/{token}/file", headers={"Range": "bytes=0-9"})

    assert reponse.status_code == 206
    assert reponse.headers["accept-ranges"] == "bytes"
    assert reponse.content == b"%PDF-1.4\nA"


def test_fichier_introuvable_404(client, article):
    token = client.post(f"/api/articles/{article.id}/share").json()["token"]
    app.dependency_overrides.pop(get_current_user, None)

    reponse = client.get(f"/api/partage/{token}/file")

    assert reponse.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_partage.py -v`
Expected: FAIL sur les 5 nouveaux tests (route `/api/partage/*` inexistante → 404 générique de FastAPI, mais les assertions sur le corps/en-têtes échouent)

- [ ] **Step 3: Write minimal implementation**

Dans `backend/app/schemas.py` :

```python
class PartageOut(BaseModel):
    article_title: str
    magazine_title: str
    collection_name: str | None
    start_page: int
    end_page: int | None
```

Créer `backend/app/routers/partage.py` :

```python
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Article
from app.schemas import PartageOut
from app.services.pdf_streaming import CACHE_PDF, resoudre_chemin_pdf, servir_pdf

# Delibere : AUCUNE Depends(get_current_user) sur ce routeur. C'est le seul
# point d'entree de l'application accessible sans session — tout son interet
# est la : un lien envoye par un canal prive (WhatsApp) doit s'ouvrir sans
# qu'on demande un compte a la personne qui le recoit.
router = APIRouter()


def _get_article_ou_404(token: str, db: Session) -> Article:
    article = db.query(Article).filter(Article.share_token == token).first()
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
```

Dans `backend/app/main.py`, ajouter l'import et l'enregistrement (à côté des autres `include_router`) :

```python
from app.routers import partage
# ...
app.include_router(partage.router, prefix="/api/partage", tags=["partage"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_partage.py -v`
Expected: 8 passed (3 de la Task 3 + 5 nouveaux)

- [ ] **Step 5: Vérifier l'ensemble de la suite et l'import**

Run (depuis `backend/`) :
```bash
python3 -c "import app.main; print('import OK')"
pytest -q
```
Expected: `import OK`, suite complète verte.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas.py backend/app/routers/partage.py backend/app/main.py backend/tests/test_partage.py
git commit -m "feat(partage): routeur public de consultation (métadonnées + fichier)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 5: Middleware — autoriser `/partage/*` sans session

Sans cette tâche, le middleware Next.js existant redirige **tout** vers `/login` sauf `/login` lui-même — la page publique de la Task 7 serait inaccessible. C'est la découverte la plus critique de ce plan : à vérifier en premier parmi les tâches frontend, avant même d'écrire la page.

**Files:**
- Modify: `frontend/middleware.ts`

**Interfaces:**
- Produces: `/partage/*` accessible sans cookie de session, et un utilisateur déjà connecté qui l'ouvre n'est PAS redirigé ailleurs (contrairement à `/login`).

- [ ] **Step 1: Modifier le middleware**

Remplacer le contenu de `frontend/middleware.ts` par :

```typescript
import { NextRequest, NextResponse } from "next/server";

// /login redirige un utilisateur deja connecte vers / : rester sur l'ecran
// de connexion une fois authentifie n'aurait aucun sens.
const PUBLIC_REDIRECT_IF_AUTHENTICATED = ["/login"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = request.cookies.has("session");

  // Lien de partage : accessible sans compte, et un utilisateur deja
  // connecte doit pouvoir l'ouvrir normalement — pas de redirection vers /
  // comme pour /login, ce serait une vraie regression pour quelqu'un qui
  // recoit son propre lien alors qu'il est connecte sur un autre onglet.
  if (pathname.startsWith("/partage/")) {
    return NextResponse.next();
  }

  if (PUBLIC_REDIRECT_IF_AUTHENTICATED.includes(pathname)) {
    if (hasSession) {
      return NextResponse.redirect(new URL("/", request.url));
    }
    return NextResponse.next();
  }

  if (!hasSession) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  // /api/* est relaye tel quel vers le backend (voir rewrites dans
  // next.config.js) et a sa propre authentification via le cookie de
  // session/JWT - ce middleware de redirection au niveau page ne doit
  // jamais l'intercepter.
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
```

- [ ] **Step 2: Vérifier les types**

Run: `npx tsc --noEmit -p .` (depuis `frontend/`)
Expected: aucune erreur.

- [ ] **Step 3: Vérification manuelle**

Démarrer le serveur de dev (`npm run dev` dans `frontend/`, backend déjà lancé séparément), puis dans un navigateur **sans être connecté** (session déconnectée / navigation privée) :
- Ouvrir `/partage/nimporte-quoi` → doit afficher la page (même si elle plante faute d'implémentation à ce stade — l'important est qu'elle n'y soit PAS redirigée vers `/login`).
- Ouvrir `/` → doit toujours rediriger vers `/login` comme avant (non-régression).

- [ ] **Step 4: Commit**

```bash
git add frontend/middleware.ts
git commit -m "fix(partage): autoriser /partage/* sans session dans le middleware

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 6: `PdfViewer` — désactiver le pré-chargement de fond

**Files:**
- Modify: `frontend/components/viewer/PdfViewer.tsx`

**Interfaces:**
- Consumes: rien de nouveau (composant déjà existant)
- Produces: nouveau prop `PdfViewer({ ..., disableAutoFetch?: boolean })`, défaut `false` — comportement du lecteur authentifié strictement inchangé.

- [ ] **Step 1: Ajouter le prop et le passer à pdf.js**

Dans `frontend/components/viewer/PdfViewer.tsx`, ajuster l'interface et l'appel à `getDocument` (vérifier d'abord le nom exact du prop interne où `fileUrl`/`withCredentials` sont actuellement passés, autour de la ligne 151 identifiée en conception) :

```typescript
interface PdfViewerProps {
  fileUrl: string;
  pageNumber: number;
  zoom: number;
  highlightWords: WordBox[];
  onPageCount?: (count: number) => void;
  onVisiblePageChange?: (page: number) => void;
  // Par defaut false : le lecteur authentifie precharge le reste du
  // document en tache de fond une fois les pages visibles rendues (confort
  // pour qui va continuer a lire). Sur la page de partage (Task 7), on le
  // desactive : seules les pages reellement consultees doivent jamais etre
  // demandees au serveur, jamais le magazine entier.
  disableAutoFetch?: boolean;
}
```

```typescript
export default function PdfViewer({
  fileUrl,
  pageNumber,
  zoom,
  highlightWords,
  onPageCount,
  onVisiblePageChange,
  disableAutoFetch = false,
}: PdfViewerProps) {
```

Et dans l'appel à `pdfjsLib.getDocument` :

```typescript
const loadedDoc = await pdfjsLib.getDocument({
  url: fileUrl,
  withCredentials: true,
  disableAutoFetch,
}).promise;
```

- [ ] **Step 2: Vérifier les types**

Run: `npx tsc --noEmit -p .` (depuis `frontend/`)
Expected: aucune erreur.

- [ ] **Step 3: Vérification manuelle de non-régression**

Ouvrir le lecteur authentifié existant (`/viewer/{id}/1`) sur un vrai magazine : la navigation page par page doit se comporter exactement comme avant (le prop n'est pas passé ici, donc `disableAutoFetch` reste `false`).

- [ ] **Step 4: Commit**

```bash
git add frontend/components/viewer/PdfViewer.tsx
git commit -m "feat(partage): PdfViewer — prop disableAutoFetch

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 7: Page publique de consultation

**Files:**
- Create: `frontend/app/partage/[token]/page.tsx`

**Interfaces:**
- Consumes: `GET /api/partage/{token}` (Task 4), `GET /api/partage/{token}/file` (Task 4), `PdfViewer` avec `disableAutoFetch` (Task 6), middleware public (Task 5)

- [ ] **Step 1: Écrire la page**

Créer `frontend/app/partage/[token]/page.tsx` :

```typescript
"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, ApiError, fileUrl } from "@/lib/api";
import Icon from "@/components/ui/Icon";
import PdfViewer from "@/components/viewer/PdfViewer";

interface PartageInfo {
  article_title: string;
  magazine_title: string;
  collection_name: string | null;
  start_page: number;
  end_page: number | null;
}

export default function PartagePage() {
  const params = useParams<{ token: string }>();
  const token = params.token;

  const [info, setInfo] = useState<PartageInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pageNumber, setPageNumber] = useState<number | null>(null);
  const [pageCount, setPageCount] = useState<number | null>(null);
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    api
      .get<PartageInfo>(`/partage/${token}`)
      .then((d) => {
        setInfo(d);
        setPageNumber(d.start_page);
      })
      .catch((err) => {
        setError(err instanceof ApiError ? "Ce lien n'est plus disponible." : "Erreur de chargement.");
      });
  }, [token]);

  if (error) {
    return (
      <div className="flex h-screen items-center justify-center bg-background p-8 text-center text-sm text-foreground-muted">
        {error}
      </div>
    );
  }

  if (!info || pageNumber === null) {
    return (
      <div className="flex h-screen items-center justify-center bg-background text-sm text-foreground-muted">
        Chargement...
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col bg-background">
      <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-outline-variant bg-surface/80 px-4 backdrop-blur-md">
        <div className="min-w-0">
          <p className="truncate font-serif text-sm font-semibold text-foreground">{info.article_title}</p>
          <p className="truncate text-xs text-foreground-muted">
            {info.magazine_title}
            {info.collection_name ? ` · ${info.collection_name}` : ""}
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-1">
          <button
            onClick={() => setZoom((z) => Math.max(0.5, +(z - 0.25).toFixed(2)))}
            className="rounded-lg p-1.5 text-foreground-muted transition hover:bg-surface-hover hover:text-foreground"
          >
            <Icon name="remove" />
          </button>
          <span className="w-12 text-center font-mono text-xs text-foreground-muted">{Math.round(zoom * 100)}%</span>
          <button
            onClick={() => setZoom((z) => Math.min(2.5, +(z + 0.25).toFixed(2)))}
            className="rounded-lg p-1.5 text-foreground-muted transition hover:bg-surface-hover hover:text-foreground"
          >
            <Icon name="add" />
          </button>

          <div className="mx-2 h-5 w-px bg-outline-variant" />

          <button
            onClick={() => setPageNumber((p) => Math.max(1, (p ?? 1) - 1))}
            disabled={pageNumber <= 1}
            className="rounded-lg p-1.5 text-foreground-muted transition hover:bg-surface-hover hover:text-foreground disabled:opacity-30"
          >
            <Icon name="chevron_left" />
          </button>
          <span className="font-mono text-xs text-foreground-muted">
            {pageNumber} / {pageCount || "—"}
          </span>
          <button
            onClick={() => setPageNumber((p) => Math.min(pageCount ?? (p ?? 1), (p ?? 1) + 1))}
            disabled={!pageCount || pageNumber >= pageCount}
            className="rounded-lg p-1.5 text-foreground-muted transition hover:bg-surface-hover hover:text-foreground disabled:opacity-30"
          >
            <Icon name="chevron_right" />
          </button>
        </div>
      </header>

      <div className="relative flex-1 overflow-hidden">
        <PdfViewer
          fileUrl={fileUrl(`/partage/${token}/file`)}
          pageNumber={pageNumber}
          zoom={zoom}
          highlightWords={[]}
          onPageCount={setPageCount}
          onVisiblePageChange={setPageNumber}
          disableAutoFetch
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Vérifier les types**

Run: `npx tsc --noEmit -p .` (depuis `frontend/`)
Expected: aucune erreur.

- [ ] **Step 3: Vérification manuelle de bout en bout**

Backend et frontend démarrés, base contenant au moins un magazine avec sommaire :
1. Appeler `POST /api/articles/{id}/share` (via l'onglet réseau du navigateur, ou `curl -X POST` avec un cookie de session valide) pour un article réel, récupérer le `token`.
2. Ouvrir `/partage/{token}` dans une fenêtre de navigation privée (donc sans cookie de session).
3. Vérifier : la page s'affiche directement sur la bonne page de l'article (pas de redirection vers `/login`), le titre/magazine/collection sont corrects, la navigation page par page et le zoom fonctionnent.
4. Ouvrir l'onglet réseau : vérifier que les requêtes vers `/api/partage/{token}/file` portent un en-tête `Range` et reçoivent des réponses `206`, pas un unique `200` qui chargerait tout le fichier.
5. Ouvrir `/partage/un-token-invalide` → doit afficher "Ce lien n'est plus disponible."

- [ ] **Step 4: Commit**

```bash
git add frontend/app/partage/
git commit -m "feat(partage): page publique de consultation d'un article

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 8: Composant réutilisable `ShareArticleButton`

**Files:**
- Create: `frontend/components/articles/ShareArticleButton.tsx`

**Interfaces:**
- Consumes: `POST /api/articles/{id}/share` (Task 3)
- Produces: `<ShareArticleButton articleId={number} className?={string} />` — composant autonome, copie le lien dans le presse-papiers au clic.

- [ ] **Step 1: Écrire le composant**

Créer `frontend/components/articles/ShareArticleButton.tsx` :

```typescript
"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import Icon from "@/components/ui/Icon";

export default function ShareArticleButton({
  articleId,
  className = "",
}: {
  articleId: number;
  className?: string;
}) {
  const [copie, setCopie] = useState(false);

  async function partager(e: React.MouseEvent) {
    // Les listes qui utilisent ce bouton l'imbriquent dans une zone
    // cliquable plus large (toute la ligne ouvre l'article) : sans ceci, le
    // clic sur "Partager" ouvrirait aussi l'article.
    e.preventDefault();
    e.stopPropagation();

    try {
      const { token } = await api.post<{ token: string }>(`/articles/${articleId}/share`);
      const url = `${window.location.origin}/partage/${token}`;
      await navigator.clipboard.writeText(url);
      setCopie(true);
      window.setTimeout(() => setCopie(false), 1500);
    } catch {
      // Silencieux : un clic raté sur un geste secondaire comme celui-ci ne
      // justifie pas une bannière d'erreur, l'utilisateur peut simplement
      // recliquer.
    }
  }

  return (
    <button
      onClick={partager}
      title={copie ? "Lien copié" : "Partager cet article"}
      className={`text-foreground-muted hover:text-foreground ${className}`}
    >
      <Icon name={copie ? "check" : "share"} className="text-sm" />
    </button>
  );
}
```

- [ ] **Step 2: Vérifier les types**

Run: `npx tsc --noEmit -p .` (depuis `frontend/`)
Expected: aucune erreur.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/articles/ShareArticleButton.tsx
git commit -m "feat(partage): composant ShareArticleButton

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 9: Brancher le bouton dans le panneau du lecteur

**Files:**
- Modify: `frontend/components/viewer/ViewerMetaPanel.tsx`

**Interfaces:**
- Consumes: `ShareArticleButton` (Task 8)

- [ ] **Step 1: Ajouter le bouton à chaque ligne d'article**

Dans `frontend/components/viewer/ViewerMetaPanel.tsx`, ajouter l'import :

```typescript
import ShareArticleButton from "@/components/articles/ShareArticleButton";
```

Remplacer le bloc de la liste des articles (le `<li>` existant) :

```typescript
        <ul className="space-y-1">
          {articles?.map((article) => (
            <li
              key={article.id}
              className="group flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-surface-hover"
            >
              <button onClick={() => onGoToPage(article.start_page)} className="min-w-0 flex-1 truncate text-left text-foreground">
                <span className="mr-2 font-mono text-[10px] tabular-nums text-foreground-muted">p.{article.start_page}</span>
                {article.title}
              </button>
              <span className="hidden shrink-0 items-center gap-1 group-hover:flex">
                <ShareArticleButton articleId={article.id} />
                {user.is_admin && (
                  <>
                    <button onClick={() => startEdit(article)} className="text-foreground-muted hover:text-foreground">
                      <Icon name="edit" className="text-sm" />
                    </button>
                    <button onClick={() => deleteArticle(article.id)} className="text-foreground-muted hover:text-red-400">
                      <Icon name="delete" className="text-sm" />
                    </button>
                  </>
                )}
              </span>
            </li>
          ))}
          {articles?.length === 0 && magazine.toc_status === "done" && (
            <p className="text-sm text-foreground-muted">Aucun sommaire détecté.</p>
          )}
        </ul>
```

(Seul changement structurel : le `<span className="hidden shrink-0 gap-1 group-hover:flex">` devient `items-center gap-1` au lieu de `gap-1` seul — pour aligner verticalement une icône `text-sm` à côté des icônes `edit`/`delete` existantes — et `ShareArticleButton` est désormais visible pour TOUS les utilisateurs, pas seulement `user.is_admin`, contrairement à `edit`/`delete` qui restent réservés à l'admin.)

- [ ] **Step 2: Vérifier les types**

Run: `npx tsc --noEmit -p .` (depuis `frontend/`)
Expected: aucune erreur.

- [ ] **Step 3: Vérification manuelle**

Ouvrir le lecteur sur un numéro ayant un sommaire, survoler une ligne d'article : l'icône de partage apparaît pour un compte non-admin aussi (contrairement à edit/delete). Cliquer dessus copie un lien dans le presse-papiers et l'icône devient une coche brièvement.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/viewer/ViewerMetaPanel.tsx
git commit -m "feat(partage): bouton Partager dans le panneau du lecteur

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 10: Brancher le bouton dans la page "Sommaires" d'une collection

**Files:**
- Modify: `frontend/app/(app)/articles/collection/[collectionId]/page.tsx:528-546` (liste par défaut des articles d'un numéro — ni la vue filtrée par thématique ni la vue de recherche de ce même fichier ne sont touchées par cette tâche, elles restent hors périmètre)

**Interfaces:**
- Consumes: `ShareArticleButton` (Task 8)

- [ ] **Step 1: Restructurer la ligne pour sortir le bouton du lien cliquable**

Le `<li>` actuel enveloppe tout son contenu dans un seul `<Link>` ; le bouton de partage doit être un élément frère, pas un enfant du lien (sinon cliquer dessus naviguerait aussi vers le lecteur). Ajouter l'import :

```typescript
import ShareArticleButton from "@/components/articles/ShareArticleButton";
```

Remplacer ce bloc :

```typescript
                {articles.map((article) => (
                  <li key={article.id}>
                    <Link
                      href={`/viewer/${magazine.id}/${article.start_page}`}
                      className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm text-foreground hover:bg-surface/60 hover:text-primary-light"
                    >
                      <span className="min-w-0 truncate">{article.title}</span>
                      <span className="shrink-0 font-mono text-xs tabular-nums text-foreground-muted">
                        p.{article.start_page}
                        {article.end_page && article.end_page !== article.start_page ? `–${article.end_page}` : ""}
                      </span>
                    </Link>
                  </li>
                ))}
```

par :

```typescript
                {articles.map((article) => (
                  <li key={article.id} className="group flex items-center gap-2 px-4 hover:bg-surface/60">
                    <Link
                      href={`/viewer/${magazine.id}/${article.start_page}`}
                      className="flex min-w-0 flex-1 items-center justify-between gap-3 py-2.5 text-sm text-foreground hover:text-primary-light"
                    >
                      <span className="min-w-0 truncate">{article.title}</span>
                      <span className="shrink-0 font-mono text-xs tabular-nums text-foreground-muted">
                        p.{article.start_page}
                        {article.end_page && article.end_page !== article.start_page ? `–${article.end_page}` : ""}
                      </span>
                    </Link>
                    <ShareArticleButton
                      articleId={article.id}
                      className="hidden shrink-0 group-hover:block"
                    />
                  </li>
                ))}
```

- [ ] **Step 2: Vérifier les types**

Run: `npx tsc --noEmit -p .` (depuis `frontend/`)
Expected: aucune erreur.

- [ ] **Step 3: Vérification manuelle**

Ouvrir la page "Sommaires" d'une collection, survoler une ligne d'article : le bouton de partage apparaît à droite, le clic dessus ne navigue pas vers le lecteur (seul un clic sur le titre le fait), et copie le lien.

- [ ] **Step 4: Commit**

```bash
git add "frontend/app/(app)/articles/collection/[collectionId]/page.tsx"
git commit -m "feat(partage): bouton Partager dans la page Sommaires d'une collection

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Après l'implémentation

Mettre à jour `README.md` (section *Fonctionnalités* et *Utilisation*) pour documenter le partage par lien — comme pour chaque fonctionnalité précédente de ce projet, cette mise à jour fait partie du prochain cycle "commit" explicitement demandé par l'utilisateur, pas de ce plan. Ne pas pousser (`git push`) tant que l'utilisateur ne l'a pas demandé : chaque tâche ci-dessus commit localement, mais l'intégration (push, CI, merge de la release) suit la règle du projet ("tu m'agrèges les modifications, et tu les commits quand je te l'indique").
