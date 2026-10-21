"""Tâche worker de classification : déclenchement, verrou et reprise."""

from datetime import datetime, timedelta, timezone

import pytest
from faux_redis import FauxRedis, Horloge

from app.services.gemini_quota import QUOTA_JOUR, Pause
from app.worker import tasks


class FausseFile:
    def __init__(self):
        self.enqueue_appels = []
        self.enqueue_at_appels = []

    def enqueue(self, *args, **kwargs):
        self.enqueue_appels.append((args, kwargs))

    def enqueue_at(self, *args, **kwargs):
        self.enqueue_at_appels.append((args, kwargs))


class FausseSession:
    fermee = False

    def close(self):
        FausseSession.fermee = True


@pytest.fixture
def env(monkeypatch):
    redis = FauxRedis(Horloge())
    file = FausseFile()
    appels = []
    monkeypatch.setattr(tasks, "redis_conn", redis)
    monkeypatch.setattr(tasks, "ingestion_queue", file)
    monkeypatch.setattr(tasks, "SessionLocal", FausseSession)
    monkeypatch.setattr(tasks.settings, "gemini_api_key", "cle-de-test")
    FausseSession.fermee = False

    def classer(resultat):
        def _classer(db, suivi, appeler):
            appels.append((db, suivi, appeler))
            if isinstance(resultat, Exception):
                raise resultat
            return {"rattaches": 0, "crees": 0, **resultat}

        monkeypatch.setattr(tasks, "classer_orphelins", _classer)

    return redis, file, appels, classer


def test_sans_cle_api_rien_n_est_mis_en_file_ni_execute(env, monkeypatch):
    redis, file, appels, classer = env
    monkeypatch.setattr(tasks.settings, "gemini_api_key", "")
    classer({"pause": None, "restants": 0})

    tasks.declencher_classification()
    tasks.classer_orphelins_task()

    assert file.enqueue_appels == []
    assert appels == []
    assert redis.get("gemini:verrou") is None


def test_declenche_une_tache_avec_une_cle(env):
    _, file, _, _ = env

    tasks.declencher_classification()

    assert file.enqueue_appels == [((tasks.classer_orphelins_task,), {"job_timeout": "30m"})]


def test_la_tache_reprogramme_la_reprise_quand_une_pause_laisse_des_articles(env):
    redis, file, appels, classer = env
    jusqua = datetime(2026, 1, 16, 8, 0, tzinfo=timezone.utc)
    classer({"pause": Pause(QUOTA_JOUR, jusqua), "restants": 3})

    tasks.classer_orphelins_task()

    assert file.enqueue_at_appels == [
        (
            (jusqua + timedelta(seconds=5), tasks.classer_orphelins_task),
            {"job_timeout": "30m"},
        )
    ]
    assert FausseSession.fermee


def test_la_tache_ne_reprogramme_rien_quand_tout_est_classe(env):
    _, file, _, classer = env
    classer({"pause": None, "restants": 0})

    tasks.classer_orphelins_task()

    assert file.enqueue_at_appels == []


def test_la_tache_ne_reprogramme_rien_si_la_pause_ne_laisse_aucun_article(env):
    _, file, _, classer = env
    classer({"pause": Pause(QUOTA_JOUR, datetime(2026, 1, 16, tzinfo=timezone.utc)), "restants": 0})

    tasks.classer_orphelins_task()

    assert file.enqueue_at_appels == []


def test_le_verrou_empeche_deux_executions_simultanees(env):
    redis, _, appels, classer = env
    classer({"pause": None, "restants": 0})
    redis.set("gemini:verrou", 1, ex=3600)

    tasks.classer_orphelins_task()

    assert appels == []
    assert redis.get("gemini:verrou") is not None  # celui de l'autre exécution, intact


def test_le_verrou_est_libere_apres_une_erreur(env):
    redis, _, _, classer = env
    classer(RuntimeError("boom"))

    with pytest.raises(RuntimeError):
        tasks.classer_orphelins_task()

    assert redis.get("gemini:verrou") is None
    assert FausseSession.fermee
