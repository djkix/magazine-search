"""Suivi de quota Gemini : les limites ne doivent jamais être dépassées."""

from datetime import datetime, timedelta, timezone

from faux_redis import FauxRedis, Horloge

from app.services.gemini_quota import (
    QUOTA_JOUR,
    QUOTA_MINUTE,
    RESERVE_JOUR,
    Pause,
    SuiviQuota,
    prochaine_reinitialisation,
)


def _suivi(horloge=None, rpm=5, rpd=20, tpm=250_000):
    horloge = horloge or Horloge()
    return SuiviQuota(FauxRedis(horloge), rpm=rpm, rpd=rpd, tpm=tpm, maintenant=horloge), horloge


def test_autorise_sous_les_limites():
    suivi, _ = _suivi()
    assert suivi.autoriser(1_000) is None


def test_refuse_quand_le_budget_du_jour_est_atteint():
    suivi, horloge = _suivi()
    for _ in range(20 - RESERVE_JOUR):
        suivi.enregistrer(10)
        horloge.maintenant += timedelta(minutes=2)  # reste sous la limite par minute
    pause = suivi.autoriser(10)
    assert pause == Pause(QUOTA_JOUR, prochaine_reinitialisation(horloge.maintenant))


def test_refuse_a_la_sixieme_requete_de_la_minute():
    horloge = Horloge(datetime(2026, 1, 15, 12, 0, 20, tzinfo=timezone.utc))
    suivi, _ = _suivi(horloge)
    for _ in range(5):
        assert suivi.autoriser(10) is None
        suivi.enregistrer(10)
    pause = suivi.autoriser(10)
    assert pause == Pause(QUOTA_MINUTE, datetime(2026, 1, 15, 12, 1, tzinfo=timezone.utc))


def test_refuse_si_les_tokens_depassent_la_minute():
    horloge = Horloge(datetime(2026, 1, 15, 12, 0, 20, tzinfo=timezone.utc))
    suivi, _ = _suivi(horloge, tpm=1_000)
    suivi.enregistrer(900)
    pause = suivi.autoriser(200)
    assert pause == Pause(QUOTA_MINUTE, datetime(2026, 1, 15, 12, 1, tzinfo=timezone.utc))


def test_la_minute_suivante_remet_les_compteurs_a_zero():
    horloge = Horloge(datetime(2026, 1, 15, 12, 0, 20, tzinfo=timezone.utc))
    suivi, _ = _suivi(horloge)
    for _ in range(5):
        suivi.enregistrer(10)
    horloge.maintenant += timedelta(minutes=1)
    assert suivi.autoriser(10) is None


def test_compteur_du_jour_repart_apres_minuit_pacifique_en_hiver():
    horloge = Horloge(datetime(2026, 1, 15, 7, 59, tzinfo=timezone.utc))  # 23:59 PST
    suivi, _ = _suivi(horloge)
    suivi.enregistrer(10)
    assert suivi.requetes_aujourdhui() == 1
    horloge.maintenant = datetime(2026, 1, 15, 8, 1, tzinfo=timezone.utc)  # 00:01 PST
    assert suivi.requetes_aujourdhui() == 0


def test_compteur_du_jour_repart_apres_minuit_pacifique_en_ete():
    horloge = Horloge(datetime(2026, 7, 15, 6, 59, tzinfo=timezone.utc))  # 23:59 PDT
    suivi, _ = _suivi(horloge)
    suivi.enregistrer(10)
    assert suivi.requetes_aujourdhui() == 1
    horloge.maintenant = datetime(2026, 7, 15, 7, 1, tzinfo=timezone.utc)  # 00:01 PDT
    assert suivi.requetes_aujourdhui() == 0


def test_prochaine_reinitialisation_gere_le_changement_d_heure():
    veille = datetime(2026, 3, 7, 20, 0, tzinfo=timezone.utc)  # 12:00 PST
    assert prochaine_reinitialisation(veille) == datetime(2026, 3, 8, 8, 0, tzinfo=timezone.utc)
    lendemain = datetime(2026, 3, 8, 20, 0, tzinfo=timezone.utc)  # 13:00 PDT
    assert prochaine_reinitialisation(lendemain) == datetime(2026, 3, 9, 7, 0, tzinfo=timezone.utc)


def test_pause_posee_est_relue_puis_expire():
    suivi, horloge = _suivi()
    jusqua = horloge.maintenant + timedelta(minutes=30)
    suivi.poser_pause("cle_invalide", jusqua)
    assert suivi.pause_active() == Pause("cle_invalide", jusqua)
    assert suivi.autoriser(10) == Pause("cle_invalide", jusqua)
    horloge.maintenant = jusqua + timedelta(seconds=1)
    assert suivi.pause_active() is None
    assert suivi.autoriser(10) is None
