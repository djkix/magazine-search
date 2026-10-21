"""Classification automatique des articles orphelins par Gemini.

Aucun appel réseau : le modèle est simulé par une fonction Python.
"""

from sqlalchemy import select

from app.models import subtheme_articles
from app.services.import_sous_thematiques import rattacher, rattacher_magazine


def _sources(db, sous_theme_id):
    lignes = db.execute(
        select(subtheme_articles.c.article_id, subtheme_articles.c.source).where(
            subtheme_articles.c.subtheme_id == sous_theme_id
        )
    ).all()
    return {article_id: source for article_id, source in lignes}


def test_rattacher_magazine_preserve_les_liens_gemini(db_taxonomie, fabrique):
    theme = fabrique.theme("Jardin")
    sous_theme = fabrique.sous_theme(theme, "Potager", ["potager"])
    magazine = fabrique.magazine()
    a = fabrique.article("Une idée sans rapport apparent", magazine)
    b = fabrique.article("Un titre sans mot-clé", magazine)
    c = fabrique.article("Réussir son potager en ville", magazine)
    fabrique.lier(sous_theme, a, source="gemini")
    fabrique.lier(sous_theme, b, source="mots_cles")

    rattacher_magazine(db_taxonomie, magazine.id)

    sources = _sources(db_taxonomie, sous_theme.id)
    assert sources[a.id] == "gemini"
    assert b.id not in sources
    assert sources[c.id] == "mots_cles"


def test_rattacher_preserve_les_liens_gemini(db_taxonomie, fabrique):
    theme = fabrique.theme("Jardin")
    sous_theme = fabrique.sous_theme(theme, "Potager", ["potager"])
    a = fabrique.article("Une idée sans rapport apparent")
    b = fabrique.article("Un titre sans mot-clé")
    fabrique.lier(sous_theme, a, source="gemini")
    fabrique.lier(sous_theme, b, source="mots_cles")

    rattacher(db_taxonomie, sous_theme, [(a.id, a.title), (b.id, b.title)], appliquer=True)

    sources = _sources(db_taxonomie, sous_theme.id)
    assert sources == {a.id: "gemini"}


# ---- Tâche 3 : sélection, lots, requête, application de la réponse ----

from app.models import Article, Subtheme  # noqa: E402
from app.services.classification_gemini import (  # noqa: E402
    ArticleACLasser,
    appliquer_reponse,
    articles_a_classer,
    construire_requete,
    decouper_en_lots,
    estimer_tokens,
    mots_cles_valides,
    taxonomie_pour_requete,
)


def _lot(articles, collection="sans collection"):
    return [ArticleACLasser(a.id, a.title, collection) for a in articles]


def test_articles_a_classer_exclut_les_rattaches_et_les_deja_soumis(db_taxonomie, fabrique):
    from sqlalchemy.sql import func

    theme = fabrique.theme("Jardin")
    sous_theme = fabrique.sous_theme(theme, "Potager", ["potager"])
    rattache = fabrique.article("Déjà rattaché")
    soumis = fabrique.article("Déjà soumis")
    libre = fabrique.article("À classer", fabrique.magazine(fabrique.collection("Maison")))
    sans_collection = fabrique.article("À classer aussi")
    fabrique.lier(sous_theme, rattache)
    soumis.classe_par_gemini_le = func.now()
    db_taxonomie.flush()

    resultat = articles_a_classer(db_taxonomie)

    assert resultat == [
        ArticleACLasser(libre.id, "À classer", "Maison"),
        ArticleACLasser(sans_collection.id, "À classer aussi", "sans collection"),
    ]


def test_taxonomie_pour_requete_borne_les_mots_cles_et_liste_les_themes_vides(
    db_taxonomie, fabrique
):
    theme = fabrique.theme("Jardin")
    fabrique.theme("Vide")
    fabrique.sous_theme(theme, "Potager", ["a1", "b2", "c3", "d4", "e5", "f6", "g7"])

    taxonomie = taxonomie_pour_requete(db_taxonomie)

    assert [t["thematique"] for t in taxonomie] == ["Jardin", "Vide"]
    sous = taxonomie[0]["sous_thematiques"][0]
    assert sous["nom"] == "Potager"
    assert sous["mots_cles"] == ["a1", "b2", "c3", "d4", "e5"]
    assert taxonomie[1]["sous_thematiques"] == []


def test_estimer_tokens_compte_un_token_pour_quatre_caracteres():
    assert estimer_tokens("") == 0
    assert estimer_tokens("abcd") == 1
    assert estimer_tokens("abcde") == 2


def test_decouper_en_lots_respecte_la_taille_maximale():
    articles = [ArticleACLasser(i, f"Titre {i}", "c") for i in range(1000)]

    lots = decouper_en_lots(articles, [])

    assert [len(lot) for lot in lots] == [300, 300, 300, 100]
    assert [a.id for lot in lots for a in lot] == list(range(1000))


def test_decouper_en_lots_respecte_le_plafond_de_tokens():
    taxonomie = [{"thematique": "Jardin", "sous_thematiques": []}]
    articles = [ArticleACLasser(i, "mot " * 1000, "c") for i in range(200)]

    lots = decouper_en_lots(articles, taxonomie)

    assert len(lots) > 1
    for lot in lots:
        assert estimer_tokens(construire_requete(taxonomie, lot)) <= 100_000


def test_construire_requete_contient_taxonomie_articles_et_consigne_de_reutilisation():
    taxonomie = [
        {
            "thematique": "Jardin",
            "sous_thematiques": [{"id": 7, "nom": "Potager", "mots_cles": ["potager"]}],
        }
    ]
    lot = [ArticleACLasser(42, "Réussir son potager", "Maison")]

    requete = construire_requete(taxonomie, lot)

    assert "Potager" in requete and '"id": 7' in requete
    assert "Réussir son potager" in requete and "42" in requete and "Maison" in requete
    assert "réutilise une sous-thématique existante" in requete


def test_mots_cles_valides_borne_et_filtre():
    mots = ["Alpha", "bravo", "charlie", "delta1", "echo22", "foxtrot", "golf33", "hotel4", "india5"]
    assert mots_cles_valides(mots, []) == [
        "alpha", "bravo", "charlie", "delta1", "echo22", "foxtrot", "golf33", "hotel4",
    ]
    assert mots_cles_valides(["abc", "  Jardin  ", "jardin"], []) == ["jardin"]


def test_mots_cles_valides_ecarte_un_mot_present_dans_plus_de_2_pour_cent_des_titres():
    titres = ["cuisine facile"] * 10 + ["titre sans rapport numero %d" % i for i in range(190)]

    assert mots_cles_valides(["cuisine", "rarissime"], titres) == ["rarissime"]


def test_appliquer_reponse_rattache_a_une_sous_thematique_existante(db_taxonomie, fabrique):
    theme = fabrique.theme("Jardin")
    sous_theme = fabrique.sous_theme(theme, "Potager", ["potager"])
    article = fabrique.article("Idée de récolte")

    bilan = appliquer_reponse(
        db_taxonomie,
        _lot([article]),
        [{"article_id": article.id, "sous_thematique_id": sous_theme.id}],
    )

    assert bilan == {"rattaches": 1, "crees": 0}
    assert _sources(db_taxonomie, sous_theme.id) == {article.id: "gemini"}


def test_appliquer_reponse_cree_une_sous_thematique_sous_une_thematique_existante(
    db_taxonomie, fabrique
):
    theme = fabrique.theme("Jardin")
    article = fabrique.article("Cultiver des orchidées")

    bilan = appliquer_reponse(
        db_taxonomie,
        _lot([article]),
        [
            {
                "article_id": article.id,
                "nouvelle": {
                    "thematique": "jardin",
                    "nom": "Orchidées",
                    "mots_cles": ["Orchidée", "orchidees"],
                },
            }
        ],
    )

    assert bilan == {"rattaches": 1, "crees": 1}
    cree = db_taxonomie.query(Subtheme).filter_by(name="Orchidées").one()
    assert cree.theme_id == theme.id
    assert cree.keywords == ["orchidée", "orchidees"]
    assert _sources(db_taxonomie, cree.id) == {article.id: "gemini"}


def test_appliquer_reponse_reutilise_une_sous_thematique_au_nom_equivalent(
    db_taxonomie, fabrique
):
    fabrique.theme("Jardin")
    a = fabrique.article("Premier")
    b = fabrique.article("Deuxième")
    c = fabrique.article("Troisième")

    def nouvelle(nom):
        return {"thematique": "Jardin", "nom": nom, "mots_cles": ["bio"]}

    appliquer_reponse(db_taxonomie, _lot([a]), [{"article_id": a.id, "nouvelle": nouvelle("Jardin Bio")}])
    appliquer_reponse(db_taxonomie, _lot([b]), [{"article_id": b.id, "nouvelle": nouvelle("jardin bio")}])
    bilan = appliquer_reponse(
        db_taxonomie, _lot([c]), [{"article_id": c.id, "nouvelle": nouvelle("Jardín  Bio")}]
    )

    assert bilan["crees"] == 0
    assert db_taxonomie.query(Subtheme).count() == 1


def test_appliquer_reponse_refuse_une_thematique_inconnue(db_taxonomie, fabrique):
    article = fabrique.article("Sujet orphelin")

    bilan = appliquer_reponse(
        db_taxonomie,
        _lot([article]),
        [
            {
                "article_id": article.id,
                "nouvelle": {"thematique": "Inventée", "nom": "X", "mots_cles": ["xxxx"]},
            }
        ],
    )

    assert bilan == {"rattaches": 0, "crees": 0}
    assert db_taxonomie.query(Subtheme).count() == 0
    assert db_taxonomie.get(Article, article.id).classe_par_gemini_le is not None


def test_appliquer_reponse_ignore_les_ids_hors_lot_ou_inconnus(db_taxonomie, fabrique):
    theme = fabrique.theme("Jardin")
    sous_theme = fabrique.sous_theme(theme, "Potager", ["potager"])
    dans_le_lot = fabrique.article("Dans le lot")
    hors_lot = fabrique.article("Hors lot")

    bilan = appliquer_reponse(
        db_taxonomie,
        _lot([dans_le_lot]),
        [
            {"article_id": hors_lot.id, "sous_thematique_id": sous_theme.id},
            {"article_id": 99999, "sous_thematique_id": sous_theme.id},
            {"article_id": dans_le_lot.id, "sous_thematique_id": 99999},
            "pas un objet",
            {"article_id": "texte", "sous_thematique_id": sous_theme.id},
        ],
    )

    assert bilan == {"rattaches": 0, "crees": 0}
    assert _sources(db_taxonomie, sous_theme.id) == {}
    assert db_taxonomie.get(Article, hors_lot.id).classe_par_gemini_le is None


def test_appliquer_reponse_horodate_tout_le_lot(db_taxonomie, fabrique):
    theme = fabrique.theme("Jardin")
    sous_theme = fabrique.sous_theme(theme, "Potager", ["potager"])
    classe = fabrique.article("Classé")
    oublie = fabrique.article("Oublié par le modèle")

    appliquer_reponse(
        db_taxonomie,
        _lot([classe, oublie]),
        [{"article_id": classe.id, "sous_thematique_id": sous_theme.id}],
    )

    assert db_taxonomie.get(Article, classe.id).classe_par_gemini_le is not None
    assert db_taxonomie.get(Article, oublie.id).classe_par_gemini_le is not None


# ---- Tâche 4 : boucle de classification ----

import json  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402

import pytest  # noqa: E402
from faux_redis import FauxRedis, Horloge  # noqa: E402

from app.services.classification_gemini import classer_orphelins  # noqa: E402
from app.services.gemini_quota import (  # noqa: E402
    FORMAT_INVALIDE,
    MODELE_INTROUVABLE,
    QUOTA_JOUR,
    QUOTA_MINUTE,
    ErreurGemini,
    Pause,
    SuiviQuota,
    prochaine_reinitialisation,
)

_MARQUEUR = "ARTICLES À CLASSER :\n"


def _suivi(rpm=1000, rpd=1000, tpm=10_000_000):
    horloge = Horloge()
    return SuiviQuota(FauxRedis(horloge), rpm=rpm, rpd=rpd, tpm=tpm, maintenant=horloge), horloge


class Modele:
    """Modèle simulé : une liste de réponses (texte ou exception), rejouée dans l'ordre."""

    def __init__(self, sous_theme_id, scenario=None):
        self.sous_theme_id = sous_theme_id
        self.scenario = list(scenario or [])
        self.appels = 0

    def __call__(self, prompt):
        self.appels += 1
        etape = self.scenario.pop(0) if self.scenario else "ok"
        if isinstance(etape, Exception):
            raise etape
        if etape == "ok":
            articles = json.loads(prompt.split(_MARQUEUR)[1])
            reponse = [
                {"article_id": a["article_id"], "sous_thematique_id": self.sous_theme_id}
                for a in articles
            ]
            return json.dumps(reponse), 100
        return etape, 100


@pytest.fixture
def monde(db_taxonomie, fabrique):
    theme = fabrique.theme("Jardin")
    sous_theme = fabrique.sous_theme(theme, "Potager", ["potager"])
    magazine = fabrique.magazine()
    articles = [fabrique.article(f"Titre numéro {i}", magazine) for i in range(301)]
    db_taxonomie.commit()
    return sous_theme, articles


def _liens(db):
    return db.execute(select(subtheme_articles.c.article_id)).all()


def test_classer_orphelins_traite_tous_les_lots_et_commite(db_taxonomie, monde):
    sous_theme, _ = monde
    suivi, _ = _suivi()
    modele = Modele(sous_theme.id)

    bilan = classer_orphelins(db_taxonomie, suivi, modele)

    assert modele.appels == 2
    assert bilan == {"rattaches": 301, "crees": 0, "restants": 0, "pause": None}
    db_taxonomie.rollback()
    assert len(_liens(db_taxonomie)) == 301


def test_pause_quota_jour_arrete_la_boucle_sans_appel(db_taxonomie, monde):
    sous_theme, _ = monde
    suivi, horloge = _suivi(rpd=2)  # budget effectif nul : 2 - 2 en réserve
    modele = Modele(sous_theme.id)

    bilan = classer_orphelins(db_taxonomie, suivi, modele)

    assert modele.appels == 0
    assert bilan["pause"] == Pause(QUOTA_JOUR, prochaine_reinitialisation(horloge.maintenant))
    assert bilan["restants"] == 301
    # La pause locale est aussi enregistrée : c'est elle que le tableau de bord lit.
    assert suivi.pause_active() == bilan["pause"]


def test_erreur_429_pose_la_pause_et_ne_reessaie_pas(db_taxonomie, monde):
    sous_theme, _ = monde
    suivi, horloge = _suivi()
    jusqua = horloge.maintenant + timedelta(seconds=30)
    modele = Modele(sous_theme.id, [ErreurGemini(QUOTA_MINUTE, "trop vite", jusqua)])

    bilan = classer_orphelins(db_taxonomie, suivi, modele)

    assert modele.appels == 1
    assert bilan["pause"] == Pause(QUOTA_MINUTE, jusqua)
    assert suivi.pause_active() == Pause(QUOTA_MINUTE, jusqua)
    assert bilan["restants"] == 301


def test_429_journalier_reprend_a_la_reinitialisation(db_taxonomie, monde):
    sous_theme, _ = monde
    suivi, horloge = _suivi()
    modele = Modele(sous_theme.id, [ErreurGemini(QUOTA_JOUR, "quota")])

    bilan = classer_orphelins(db_taxonomie, suivi, modele)

    assert bilan["pause"] == Pause(QUOTA_JOUR, prochaine_reinitialisation(horloge.maintenant))


def test_modele_introuvable_pose_une_pause_avec_la_raison(db_taxonomie, monde):
    sous_theme, _ = monde
    suivi, horloge = _suivi()
    modele = Modele(sous_theme.id, [ErreurGemini(MODELE_INTROUVABLE, "absent")])

    bilan = classer_orphelins(db_taxonomie, suivi, modele)

    assert bilan["pause"] == Pause(MODELE_INTROUVABLE, horloge.maintenant + timedelta(hours=1))


def test_reponse_mal_formee_compte_une_requete_et_laisse_les_articles_candidats(
    db_taxonomie, monde
):
    sous_theme, _ = monde
    suivi, _ = _suivi()
    modele = Modele(sous_theme.id, ["pas du json"])

    bilan = classer_orphelins(db_taxonomie, suivi, modele)

    # une réponse illisible, puis le lot repart divisé par deux et réussit ;
    # la moitié restante et le dernier article passent ensuite : 4 appels
    assert modele.appels == 4
    assert suivi.requetes_aujourdhui() == 4
    assert bilan["restants"] == 0


def test_trois_reponses_mal_formees_posent_une_pause_d_une_heure(db_taxonomie, monde):
    sous_theme, _ = monde
    suivi, horloge = _suivi()
    modele = Modele(sous_theme.id, ["[", "{}", "oups"])

    bilan = classer_orphelins(db_taxonomie, suivi, modele)

    assert modele.appels == 3
    assert suivi.requetes_aujourdhui() == 3
    assert bilan["pause"] == Pause(FORMAT_INVALIDE, horloge.maintenant + timedelta(hours=1))
    assert bilan["restants"] == 301


def test_une_reponse_valide_remet_le_compteur_d_echecs_a_zero(db_taxonomie, monde):
    sous_theme, _ = monde
    suivi, _ = _suivi()
    # Deux échecs, un succès, deux échecs, un succès : 4 échecs au total mais
    # jamais 3 d'affilée, donc aucune pause, et tout finit classé.
    modele = Modele(sous_theme.id, ["[", "[", "ok", "[", "[", "ok"])

    bilan = classer_orphelins(db_taxonomie, suivi, modele)

    assert bilan["pause"] is None
    assert bilan["restants"] == 0
    assert bilan["rattaches"] == 301


def test_un_echec_gemini_ne_touche_pas_aux_donnees_deja_commitees(db_taxonomie, monde):
    sous_theme, _ = monde
    suivi, horloge = _suivi()
    modele = Modele(sous_theme.id, ["ok", ErreurGemini(QUOTA_MINUTE, "stop", horloge.maintenant + timedelta(seconds=30))])

    bilan = classer_orphelins(db_taxonomie, suivi, modele)

    db_taxonomie.rollback()
    assert len(_liens(db_taxonomie)) == 300
    assert bilan["rattaches"] == 300
    assert bilan["restants"] == 1


# ---- Passe de correction après relecture ----


def test_rattacher_ne_viole_pas_la_cle_quand_un_lien_gemini_correspond_aux_mots_cles(
    db_taxonomie, fabrique
):
    theme = fabrique.theme("Energie")
    sous_theme = fabrique.sous_theme(theme, "Solaire", ["photovoltaique"])
    article = fabrique.article("Le photovoltaïque en toiture")
    fabrique.lier(sous_theme, article, source="gemini")

    rapport = rattacher(db_taxonomie, sous_theme, [(article.id, article.title)], appliquer=True)

    assert rapport["articles"] == 1
    assert _sources(db_taxonomie, sous_theme.id) == {article.id: "gemini"}


def test_appliquer_reponse_refuse_un_nom_trop_long_pour_la_base(db_taxonomie, fabrique):
    fabrique.theme("Jardin")
    article = fabrique.article("Sujet")

    bilan = appliquer_reponse(
        db_taxonomie,
        _lot([article]),
        [
            {
                "article_id": article.id,
                "nouvelle": {"thematique": "Jardin", "nom": "x" * 300, "mots_cles": ["jardin"]},
            }
        ],
    )

    assert bilan == {"rattaches": 0, "crees": 0}
    assert db_taxonomie.query(Subtheme).count() == 0


def test_un_lot_trop_gros_pour_la_reponse_est_divise_puis_tout_est_classe(db_taxonomie, monde):
    """Une réponse tronquée sur un gros lot ne doit pas bloquer la file : le
    lot est divisé à chaque échec, et ce qui n'a pas été envoyé est repris."""
    sous_theme, _ = monde
    suivi, _ = _suivi()
    ok = Modele(sous_theme.id)

    def modele_a_la_reponse_limitee(prompt):
        articles = json.loads(prompt.split(_MARQUEUR)[1])
        if len(articles) > 100:
            return '[{"article_id": 1, "sous_', 100  # réponse tronquée
        return ok(prompt)

    bilan = classer_orphelins(db_taxonomie, suivi, modele_a_la_reponse_limitee)

    assert bilan["pause"] is None
    assert bilan["restants"] == 0
    assert bilan["rattaches"] == 301
