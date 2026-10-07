"""Service de streaming de fichiers (PDF par plages HTTP, couvertures).

Aucun appel réseau, aucune base : seules les fonctions du service sont
appelées, sur un petit fichier créé pour le test. `servir_pdf` n'avait
aucune couverture automatisée avant son introduction — seulement vérifié
manuellement.
"""

import asyncio

import pytest
from fastapi import HTTPException
from starlette.datastructures import Headers

from app.models import Magazine
from app.services.media_streaming import servir_couverture, servir_pdf


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


# ---- servir_couverture ----


def _magazine_avec_couverture(chemin) -> Magazine:
    m = Magazine()
    m.cover_thumbnail_path = str(chemin)
    return m


def test_couverture_webp(tmp_path):
    chemin = tmp_path / "1.webp"
    chemin.write_bytes(b"RIFF....WEBP")

    reponse = servir_couverture(_magazine_avec_couverture(chemin))

    assert reponse.status_code == 200
    assert reponse.media_type == "image/webp"


def test_couverture_png_ancien_format(tmp_path):
    # Vignettes produites avant la bascule vers WebP : encore en PNG sur
    # disque, le type MIME doit suivre l'extension reelle du fichier.
    chemin = tmp_path / "1.png"
    chemin.write_bytes(b"\x89PNG....")

    reponse = servir_couverture(_magazine_avec_couverture(chemin))

    assert reponse.status_code == 200
    assert reponse.media_type == "image/png"


def test_couverture_absente_404():
    m = Magazine()
    m.cover_thumbnail_path = None

    with pytest.raises(HTTPException) as exc:
        servir_couverture(m)
    assert exc.value.status_code == 404


def test_couverture_fichier_manquant_404(tmp_path):
    m = _magazine_avec_couverture(tmp_path / "inexistant.webp")

    with pytest.raises(HTTPException) as exc:
        servir_couverture(m)
    assert exc.value.status_code == 404
