"""Noms de fichiers de maquette pris pour des titres d'articles.

Calcul pur : aucune base, aucun PDF — seule la fonction de nettoyage est
appelée.

Les magazines portent dans leur marge le nom du fichier InDesign qui a servi
à les composer. L'OCR le lit comme du texte ordinaire, et le parseur de
sommaire le retient soit seul comme titre, soit — plus insidieux — collé à la
fin d'un titre valide.

Les treize chaînes ci-dessous sont **authentiques** : ce sont les treize seuls
cas du corpus (13 546 articles) dont le titre contient un nom de fichier de
maquette, relevés en base avant correctif.

Deux critères plus larges ont été essayés puis abandonnés sur preuve, et les
titres de contrôle en fin de fichier servent à empêcher qu'on y revienne :

- « pas de voyelle » attrape « GT3 RS » et « GT2 RS », modèles Porsche bien
  réels dans les magazines automobiles ;
- « titre trop court » attrape « MIX », « Q&A » et « Une », rubriques tout
  aussi réelles.

Le filtre ne vise donc QUE le motif nom de fichier, et son seuil de longueur
ne s'applique qu'aux titres déjà touchés par ce motif.
"""

from app.services.sommaire_ocr import _nettoyer_titre

# Scories pures : rien d'exploitable une fois le nom de fichier retiré.
MAQUETTES_SEULES = [
    "607-sommaire.indd",
    "620-SOMMAIRE.indd",
    "625-SOMMAIRE.indd",
    "QC598-sommaire.indd",
    "QC599-sommaire.indd",
    "HS_COUV_v3.indd",
    "Couv-B35_OK v4A.indd",
    "Couv_B25 V5.indd",
    "couv fr.indd",
]

# Titres légitimes qu'un nom de fichier est venu polluer en fin de ligne.
TITRES_AGGLUTINES = [
    (
        "Les fraudes perdurent GRAND TEST ● LABO 607-sommaire.indd",
        "Les fraudes perdurent GRAND TEST ● LABO",
    ),
    (
        "les gestes et utiliser les bons outils 1 Couv-B35_OK v4A.indd",
        "les gestes et utiliser les bons outils 1 Couv-B35_OK",
    ),
]

# Titres authentiques du corpus, dont aucun ne doit être modifié. Plusieurs
# seraient détruits par un critère de brièveté ou d'absence de voyelle.
TITRES_LEGITIMES = [
    "GT3 RS",
    "GT2 RS",
    "GT3 RS vs 992 GT3",
    "GT4",
    "MIX",
    "Q&A",
    "Une",
    "NEWS",
    "SUBSCRIBE",
    "Courrier",
    "Porsche",
    "Jurisprudence",
    "Miniatures",
]


def test_une_maquette_seule_est_rejetee():
    """Rendre une chaîne vide : les appelants ignorent déjà un titre vide."""
    for titre in MAQUETTES_SEULES:
        assert _nettoyer_titre(titre) == "", titre


def test_un_titre_agglutine_est_recupere():
    """Le cas le plus dommageable : un vrai titre abîmé par le suffixe."""
    for brut, attendu in TITRES_AGGLUTINES:
        assert _nettoyer_titre(brut) == attendu


def test_les_titres_legitimes_sont_intacts():
    """Non-régression : le filtre ne doit toucher que le motif visé.

    C'est la condition qui a fait rejeter les deux critères plus larges.
    """
    for titre in TITRES_LEGITIMES:
        assert _nettoyer_titre(titre) == titre


def test_le_seuil_ne_s_applique_qu_aux_titres_touches():
    """Un titre court sans nom de fichier passe, quel que soit le seuil.

    Sans cette garantie, le seuil de 15 caractères supprimerait « MIX » et
    « Q&A », qui n'ont rien à voir avec le défaut traité.
    """
    assert _nettoyer_titre("p") == "p"
    assert _nettoyer_titre("THE") == "THE"
    assert _nettoyer_titre("Na") == "Na"


def test_autres_extensions_de_maquette():
    """Le motif ne se limite pas à InDesign : l'OCR lit ce qui est imprimé."""
    assert _nettoyer_titre("couverture_finale.pdf") == ""
    assert _nettoyer_titre("visuel_une.JPG") == ""
    assert _nettoyer_titre("planche 3.eps") == ""


def test_un_titre_contenant_un_point_n_est_pas_tronque():
    """Garde-fou : seule une extension connue déclenche le nettoyage."""
    for titre in ["Le test du 4.0 TFSI", "Version 2.0 du protocole", "M.A.O."]:
        assert _nettoyer_titre(titre) == titre
