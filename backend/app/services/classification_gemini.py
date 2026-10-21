"""Classification des articles orphelins par Gemini.

Un article est « orphelin » quand le rattachement par mots-clés ne l'a placé
dans aucune sous-thématique. Ce module prépare les lots envoyés au modèle et
applique sa réponse : rattachement à une sous-thématique existante, ou création
d'une nouvelle sous une thématique existante.

Les liens posés ici portent `source='gemini'` : le recalcul par mots-clés ne
doit pas les effacer, il ne saurait pas les retrouver.
"""

import json
import math
from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.models import Article, Collection, Magazine, Subtheme, Theme, subtheme_articles
from app.services.gemini_quota import (
    ERREUR_API,
    FORMAT_INVALIDE,
    QUOTA_JOUR,
    QUOTA_MINUTE,
    ErreurGemini,
    Pause,
    SuiviQuota,
    prochaine_reinitialisation,
)
from app.services.import_sous_thematiques import corpus_articles
from app.services.sous_thematiques import motif_du_mot_cle, normaliser

TAILLE_LOT_MAX = 300
TOKENS_REQUETE_MAX = 100_000
MOTS_CLES_MAX = 8
MOT_CLE_LONGUEUR_MIN = 4
MOT_CLE_PART_CORPUS_MAX = 0.02
# Sous ce nombre d'articles, 2 % ne veut rien dire (un corpus de 20 titres
# écarterait tout mot présent dans un seul d'entre eux).
MOT_CLE_ARTICLES_MIN = 5
MOTS_CLES_PAR_SOUS_THEMATIQUE_ENVOYES = 5
ECHECS_FORMAT_AVANT_PAUSE = 3
PAUSE_FORMAT = timedelta(hours=1)
# Reprise par défaut quand Google n'indique rien : une clé ou un modèle
# erronés ne se réparent pas seuls, mais l'heure laisse le temps de corriger la
# configuration ; une panne d'API se retente plus vite.
PAUSE_CONFIGURATION = timedelta(hours=1)
PAUSE_PANNE = timedelta(minutes=15)

# Longueur de `subthemes.name` : PostgreSQL refuse un nom plus long (SQLite non).
LONGUEUR_NOM_MAX = 255

SANS_COLLECTION = "sans collection"

CONSIGNE = (
    "Tu classes des titres d'articles de magazines dans une taxonomie à deux "
    "niveaux (thématique > sous-thématique).\n"
    "Pour CHAQUE article de la liste, réponds par un objet JSON :\n"
    "- soit {\"article_id\": N, \"sous_thematique_id\": ID} avec l'identifiant d'une "
    "sous-thématique existante ;\n"
    "- soit {\"article_id\": N, \"nouvelle\": {\"thematique\": NOM, \"nom\": NOM, "
    "\"mots_cles\": [...]}} pour proposer une nouvelle sous-thématique, "
    "uniquement sous l'une des thématiques existantes listées ci-dessous.\n"
    "Prends le temps de chercher : réutilise une sous-thématique existante si le "
    "sujet est le même, même formulé autrement. Ne propose une nouvelle "
    "sous-thématique que si aucune ne convient. Les mots-clés d'une nouvelle "
    "sous-thématique sont spécifiques (4 lettres minimum, 8 au plus) : pas de "
    "mot générique qui apparaîtrait dans des centaines de titres."
)

SCHEMA_REPONSE = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "article_id": {"type": "integer"},
            "sous_thematique_id": {"type": "integer"},
            "nouvelle": {
                "type": "object",
                "properties": {
                    "thematique": {"type": "string"},
                    "nom": {"type": "string"},
                    "mots_cles": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["thematique", "nom", "mots_cles"],
            },
        },
        "required": ["article_id"],
    },
}


class ArticleACLasser(NamedTuple):
    id: int
    titre: str
    collection: str


def articles_a_classer(db: Session) -> list[ArticleACLasser]:
    """Articles sans aucun lien et jamais soumis au modèle."""
    rattache = exists().where(subtheme_articles.c.article_id == Article.id)
    lignes = (
        db.query(Article.id, Article.title, Collection.name)
        .join(Magazine, Magazine.id == Article.magazine_id)
        .outerjoin(Collection, Collection.id == Magazine.collection_id)
        .filter(Article.classe_par_gemini_le.is_(None), ~rattache)
        .order_by(Article.id)
        .all()
    )
    return [ArticleACLasser(i, titre, collection or SANS_COLLECTION) for i, titre, collection in lignes]


def taxonomie_pour_requete(db: Session) -> list[dict]:
    """Taxonomie allégée pour la requête : tous les thèmes, même vides."""
    resultat = []
    for theme in db.query(Theme).order_by(Theme.name).all():
        sous_themes = sorted(theme.subthemes, key=lambda s: s.name)
        resultat.append(
            {
                "thematique": theme.name,
                "sous_thematiques": [
                    {
                        "id": s.id,
                        "nom": s.name,
                        "mots_cles": list(s.keywords)[:MOTS_CLES_PAR_SOUS_THEMATIQUE_ENVOYES],
                    }
                    for s in sous_themes
                ],
            }
        )
    return resultat


def estimer_tokens(texte: str) -> int:
    """Environ 4 caractères par token : suffisant pour rester sous un plafond."""
    return math.ceil(len(texte) / 4)


def construire_requete(taxonomie: list[dict], lot: list[ArticleACLasser]) -> str:
    articles = [{"article_id": a.id, "titre": a.titre, "collection": a.collection} for a in lot]
    return (
        f"{CONSIGNE}\n\nTAXONOMIE EXISTANTE :\n"
        f"{json.dumps(taxonomie, ensure_ascii=False, indent=1)}\n\nARTICLES À CLASSER :\n"
        f"{json.dumps(articles, ensure_ascii=False)}"
    )


def decouper_en_lots(
    articles: list[ArticleACLasser], taxonomie: list[dict]
) -> list[list[ArticleACLasser]]:
    """Lots d'au plus TAILLE_LOT_MAX articles et TOKENS_REQUETE_MAX tokens.

    La taxonomie part avec chaque requête : elle compte dans le plafond. Un lot
    contient toujours au moins un article, même si la taxonomie seule dépasse.
    """
    base = estimer_tokens(construire_requete(taxonomie, []))
    lots: list[list[ArticleACLasser]] = []
    courant: list[ArticleACLasser] = []
    tokens = base
    for article in articles:
        cout = estimer_tokens(construire_requete([], [article])) - estimer_tokens(
            construire_requete([], [])
        )
        if courant and (len(courant) >= TAILLE_LOT_MAX or tokens + cout > TOKENS_REQUETE_MAX):
            lots.append(courant)
            courant, tokens = [], base
        courant.append(article)
        tokens += cout
    if courant:
        lots.append(courant)
    return lots


def mots_cles_valides(mots: list[str], titres_corpus: list[str]) -> list[str]:
    """Mots-clés proposés par le modèle, nettoyés et bornés.

    Un mot trop répandu dans le corpus aspirerait des articles sans rapport lors
    du prochain recalcul : il est écarté.
    """
    titres = [normaliser(t) for t in titres_corpus]
    seuil = max(MOT_CLE_ARTICLES_MIN, MOT_CLE_PART_CORPUS_MAX * len(titres))
    retenus: list[str] = []
    for mot in mots:
        mot = str(mot).strip().lower()
        if len(mot) < MOT_CLE_LONGUEUR_MIN or mot in retenus:
            continue
        motif = motif_du_mot_cle(mot)
        if motif is None:
            continue
        if sum(1 for titre in titres if motif.search(titre)) > seuil:
            continue
        retenus.append(mot)
        if len(retenus) == MOTS_CLES_MAX:
            break
    return retenus


def _cle_nom(nom: str) -> str:
    return " ".join(normaliser(nom).split())


def appliquer_reponse(db: Session, lot: list[ArticleACLasser], reponse: list[dict]) -> dict:
    """Applique la réponse du modèle. N'effectue pas de commit.

    Tolérante : tout élément mal formé, hors lot ou pointant vers un
    identifiant inconnu est ignoré. Tous les articles du lot sont horodatés,
    rattachés ou non, pour ne pas être renvoyés au modèle indéfiniment.
    """
    ids_lot = {a.id for a in lot}
    sous_themes_connus = {s.id for s in db.query(Subtheme.id).all()}
    titres_corpus = [titre for _, titre in corpus_articles(db)]
    traites: set[int] = set()
    rattaches = crees = 0

    for element in reponse:
        if not isinstance(element, dict):
            continue
        article_id = element.get("article_id")
        if not isinstance(article_id, int) or article_id not in ids_lot or article_id in traites:
            continue

        sous_theme_id = element.get("sous_thematique_id")
        nouvelle = element.get("nouvelle")
        if isinstance(sous_theme_id, int) and sous_theme_id in sous_themes_connus:
            cible = sous_theme_id
        elif isinstance(nouvelle, dict):
            cible, cree = _sous_theme_pour(db, nouvelle, titres_corpus)
            if cible is None:
                continue
            crees += cree
            sous_themes_connus.add(cible)
        else:
            continue

        db.execute(
            subtheme_articles.insert().values(
                subtheme_id=cible, article_id=article_id, source="gemini"
            )
        )
        traites.add(article_id)
        rattaches += 1

    db.query(Article).filter(Article.id.in_(ids_lot)).update(
        {Article.classe_par_gemini_le: datetime.now(timezone.utc)}, synchronize_session=False
    )
    # L'update en masse ne met pas à jour les objets déjà chargés : on les
    # expire (après flush, rien n'est en attente) pour qu'ils relisent la base.
    db.flush()
    db.expire_all()
    return {"rattaches": rattaches, "crees": crees}


def _sous_theme_pour(db: Session, nouvelle: dict, titres_corpus: list[str]) -> tuple[int | None, int]:
    """(id de la sous-thématique, 1 si créée), ou (None, 0) si la proposition est refusée."""
    nom_theme = str(nouvelle.get("thematique") or "").strip()
    nom = str(nouvelle.get("nom") or "").strip()
    if not nom_theme or not nom or len(nom) > LONGUEUR_NOM_MAX:
        return None, 0
    theme = db.query(Theme).filter(func.lower(Theme.name) == nom_theme.lower()).first()
    if theme is None:
        return None, 0

    existante = next((s for s in theme.subthemes if _cle_nom(s.name) == _cle_nom(nom)), None)
    if existante is not None:
        return existante.id, 0

    mots = nouvelle.get("mots_cles")
    mots = mots if isinstance(mots, list) else []
    sous_theme = Subtheme(
        theme_id=theme.id, name=nom, keywords=mots_cles_valides(mots, titres_corpus)
    )
    db.add(sous_theme)
    db.flush()
    db.refresh(theme)
    return sous_theme.id, 1


def _reprise(erreur: ErreurGemini, maintenant: datetime) -> datetime:
    if erreur.raison == QUOTA_JOUR:
        return prochaine_reinitialisation(maintenant)
    if erreur.jusqua is not None:
        return erreur.jusqua
    if erreur.raison == QUOTA_MINUTE:
        return maintenant.replace(second=0, microsecond=0) + timedelta(minutes=1)
    if erreur.raison == ERREUR_API:
        return maintenant + PAUSE_PANNE
    return maintenant + PAUSE_CONFIGURATION


def _reponse_valide(texte: str) -> list | None:
    try:
        donnees = json.loads(texte)
    except (json.JSONDecodeError, TypeError):
        return None
    return donnees if isinstance(donnees, list) else None


def classer_orphelins(
    db: Session, suivi: SuiviQuota, appeler_modele: Callable[[str], tuple[str, int]]
) -> dict:
    """Classe les articles orphelins, lot par lot, dans la limite des quotas.

    Chaque lot est validé (commit) dès sa réponse appliquée : un échec ou une
    pause en cours de route ne défait jamais les lots précédents. S'arrête
    sur la première pause, que `suivi` conserve pour l'affichage.
    """
    bilan = {"rattaches": 0, "crees": 0, "restants": 0, "pause": None}

    def terminer(pause: Pause | None) -> dict:
        bilan["pause"] = pause
        bilan["restants"] = len(articles_a_classer(db))
        return bilan

    lots = deque(decouper_en_lots(articles_a_classer(db), taxonomie_pour_requete(db)))
    while lots:
        lot = lots.popleft()
        echecs = 0
        while True:
            prompt = construire_requete(taxonomie_pour_requete(db), lot)
            pause = suivi.autoriser(estimer_tokens(prompt))
            if pause is not None:
                # Enregistrée aussi quand le refus est local : c'est elle que
                # lit le tableau de bord pour annoncer la reprise.
                suivi.poser_pause(*pause)
                return terminer(pause)

            # Comptée avant l'appel : une requête partie consomme du quota,
            # qu'elle réussisse, échoue ou revienne illisible.
            suivi.enregistrer(estimer_tokens(prompt))
            try:
                texte, _ = appeler_modele(prompt)
            except ErreurGemini as erreur:
                pause = Pause(erreur.raison, _reprise(erreur, suivi.maintenant()))
                suivi.poser_pause(*pause)
                return terminer(pause)

            reponse = _reponse_valide(texte)
            if reponse is None:
                echecs += 1
                if echecs >= ECHECS_FORMAT_AVANT_PAUSE:
                    pause = Pause(FORMAT_INVALIDE, suivi.maintenant() + PAUSE_FORMAT)
                    suivi.poser_pause(*pause)
                    return terminer(pause)
                # Cause la plus probable : une réponse tronquée sur un lot trop
                # gros. On réessaie avec la moitié, le reste repasse ensuite.
                moitie = max(1, len(lot) // 2)
                if lot[moitie:]:
                    lots.appendleft(lot[moitie:])
                lot = lot[:moitie]
                continue

            resultat = appliquer_reponse(db, lot, reponse)
            db.commit()
            bilan["rattaches"] += resultat["rattaches"]
            bilan["crees"] += resultat["crees"]
            break

    return terminer(None)
