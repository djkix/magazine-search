"""Distinction entre « pas de sommaire » et « sommaire illisible ».

Calcul pur : aucune base, aucun PDF.

Les deux cas se ressemblent en base — statut terminé, zéro article — mais
appellent des actions opposées. Un numéro sans sommaire ne demande rien ; un
sommaire trouvé et non lu est un échec qui doit se voir.

Avant ce correctif, les 675 numéros sans sommaire de la bibliothèque étaient
tous marqués « terminé », y compris ceux dont la page de sommaire avait été
localisée. Un faux succès, plus insidieux qu'une erreur franche puisque rien
ne le signalait dans l'interface.

Le texte ci-dessous est **authentique** : page 6 de « Capital 389 », relevée
en production, où le diagnostic donne « Sommaire détecté (page 6) mais aucune
entrée n'a pu en être lue ». Capital compose sa page de sommaire sans aucun
numéro de page dans le flux de texte — rubrique et titre seulement — ce qui
ne laisse rien à rattacher au parseur.
"""

from app.models import Page
from app.services.sommaire_ocr import RAISON_AUCUNE_PAGE, analyser_absence_de_sommaire


def page(numero, texte):
    p = Page()
    p.page_number = numero
    p.raw_text = texte
    return p


# Page de sommaire réelle : le mot « Sommaire » est là, les entrées aussi,
# mais pas un seul numéro de page.
SOMMAIRE_SANS_NUMEROS = """Sommaire
589
Février 2024
L'interview du mois Jacques et
Marion Glénat, directeur général et
présidente du directoire de Glénat
Bientôt sur le marché
Dernière minute Hotel Maybourne:
le prochain palace parisien au cœur
d'une brouille irlando-qatarie
Un secteur à la loupe
Business Nucléaire: ils turbinent tous
pour relancer la filière
Portrait Bernard Magrez: comment
bosse le plus vieux patron de France
Succès Nescafé, le premier de la tasse
Montagne Quel avenir sans la neige?
Tribune
"""

PROSE_ORDINAIRE = """Les cliniques vétérinaires soignent aussi leur rentabilité.
Le marché a connu une consolidation rapide ces dernières années, portée par
l'arrivée de fonds d'investissement qui rachètent les cabinets indépendants.
Les praticiens y voient une réponse à la charge administrative croissante.
"""


def test_page_reperee_mais_illisible():
    """Le cas qui doit désormais compter comme un échec.

    La liste rendue est non vide : c'est elle, et non le libellé, qui pilote
    la bascule du statut en « failed » dans le worker.
    """
    pages = [page(1, PROSE_ORDINAIRE), page(6, SOMMAIRE_SANS_NUMEROS)]

    message, pages_sommaire = analyser_absence_de_sommaire(pages)

    assert pages_sommaire == [6]
    assert "6" in message


def test_aucune_page_reperee():
    """Le cas qui doit rester « terminé » : un numéro peut n'avoir aucun sommaire."""
    pages = [page(n, PROSE_ORDINAIRE) for n in range(1, 6)]

    message, pages_sommaire = analyser_absence_de_sommaire(pages)

    assert pages_sommaire == []
    assert message == RAISON_AUCUNE_PAGE


def test_la_liste_pilote_la_decision_pas_le_libelle():
    """Garde-fou contre une régression tentante.

    Déduire le cas en comparant le message à une constante marcherait
    aujourd'hui et casserait à la première reformulation du libellé. Les deux
    valeurs doivent rester cohérentes entre elles, sans que l'une se déduise
    de l'autre par analyse de texte.
    """
    vide = analyser_absence_de_sommaire([page(n, PROSE_ORDINAIRE) for n in range(1, 6)])
    trouve = analyser_absence_de_sommaire([page(6, SOMMAIRE_SANS_NUMEROS)])

    assert bool(vide[1]) is False
    assert bool(trouve[1]) is True
    assert vide[0] != trouve[0]
