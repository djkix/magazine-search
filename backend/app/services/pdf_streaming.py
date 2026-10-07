import re
from collections.abc import Iterator
from pathlib import Path

from fastapi import Request, Response, status
from fastapi.responses import FileResponse, StreamingResponse

from app.config import get_settings
from app.models import Magazine

settings = get_settings()


def resoudre_chemin_pdf(magazine: Magazine) -> Path:
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
