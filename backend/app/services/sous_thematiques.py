"""Rattachement des numéros aux sous-thématiques par correspondance de
mots-clés sur les titres d'articles.

Calcul PUR : aucune base, aucun appel réseau. C'est délibéré — un modèle de
langage nomme les regroupements hors ligne, mais le rattachement doit rester
vérifiable, explicable et rejouable gratuitement quand la bibliothèque
s'enrichit. Ce module est le cœur de cette garantie, et le seul endroit à
tester.
"""

import re
import unicodedata


def normaliser(texte: str) -> str:
    """Minuscules sans accents, pour comparer « Crème » et « creme ».

    Les titres viennent de l'OCR : la casse et les accents y sont trop
    irréguliers pour servir de critère de comparaison.
    """
    decompose = unicodedata.normalize("NFKD", texte or "")
    sans_accents = "".join(c for c in decompose if not unicodedata.combining(c))
    return sans_accents.casefold()


def motif_du_mot_cle(mot_cle: str) -> re.Pattern | None:
    """Expression régulière d'un mot-clé, ou None s'il est vide.

    Trois précautions, chacune tirée d'un cas réel :

    - **Bornes de mots.** Sans elles, « UV » correspondrait dans « ouvrir » et
      « SPF » dans n'importe quel sigle : le rattachement deviendrait du bruit.

    - **Espaces de largeur variable.** L'OCR produit fréquemment plusieurs
      espaces d'affilée entre deux mots.

    - **Tolérance au pluriel.** « crème solaire » doit correspondre à
      « les crèmes solaires au banc d'essai ». Sans le « [sx]? » final, la
      moitié des titres échappait au rattachement, la presse titrant
      massivement au pluriel. Le sur-appariement reste négligeable : une
      lettre finale facultative.
    """
    normalise = normaliser(mot_cle).strip()
    if not normalise:
        return None
    morceaux = [re.escape(m) + r"[sx]?" for m in normalise.split()]
    if not morceaux:
        return None
    return re.compile(r"\b" + r"\s+".join(morceaux) + r"\b")


def motifs_des_mots_cles(mots_cles: list[str]) -> list[re.Pattern]:
    """Motifs compilés d'une liste de mots-clés, les vides écartés."""
    motifs = [motif_du_mot_cle(m) for m in mots_cles or []]
    return [m for m in motifs if m is not None]


def mots_cles_steriles(mots_cles: list[str], titres: list[str]) -> list[str]:
    """Mots-clés ne correspondant à aucun titre du corpus.

    Signale que le modèle a inventé un regroupement absent des données. Sans
    cette remontée, la sous-thématique serait simplement vide, sans que rien
    n'explique pourquoi.
    """
    cibles = [normaliser(t) for t in titres]
    steriles = []
    for mot_cle in mots_cles or []:
        motif = motif_du_mot_cle(mot_cle)
        if motif is None:
            continue
        if not any(motif.search(c) for c in cibles):
            steriles.append(mot_cle)
    return steriles


def compter_par_numero(motifs: list[re.Pattern], articles: list[tuple[int, str]]) -> dict[int, int]:
    """Nombre d'articles correspondants, par numéro.

    Un article compte UNE fois même s'il déclenche plusieurs mots-clés : la
    grandeur affichée est « combien d'articles parlent de ça », pas « combien
    de mots-clés ont été touchés », qui récompenserait les listes verbeuses.
    """
    comptes: dict[int, int] = {}
    for magazine_id, titre in articles:
        cible = normaliser(titre)
        if any(motif.search(cible) for motif in motifs):
            comptes[magazine_id] = comptes.get(magazine_id, 0) + 1
    return comptes
