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
