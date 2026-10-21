"""Suivi des quotas de l'API Gemini, tenu dans Redis.

L'objectif est de ne jamais heurter la limite de Google : chaque requête est
autorisée AVANT de partir, et une requête refusée se traduit par une `Pause`
(raison + heure de reprise) que le tableau de bord affiche.

Le « jour » de quota est le jour du Pacifique : Google réinitialise ses
quotas quotidiens à minuit heure de Los Angeles.
"""

import json
import math
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import NamedTuple
from zoneinfo import ZoneInfo

PACIFIQUE = ZoneInfo("America/Los_Angeles")

QUOTA_JOUR = "quota_jour"
QUOTA_MINUTE = "quota_minute"
CLE_INVALIDE = "cle_invalide"
MODELE_INTROUVABLE = "modele_introuvable"
FORMAT_INVALIDE = "format_invalide"
ERREUR_API = "erreur_api"

# Requêtes gardées en réserve sur le quota du jour : d'autres usages du même
# projet Google (autres outils, essais manuels) consomment aussi le quota.
RESERVE_JOUR = 2

CLE_PAUSE = "gemini:pause"
_TTL_JOUR = 26 * 3600
_TTL_MINUTE = 120


class Pause(NamedTuple):
    raison: str
    jusqua: datetime


class ErreurGemini(Exception):
    """Échec d'un appel à Gemini, déjà traduit en raison de pause.

    `jusqua` est l'heure de reprise indiquée par Google quand elle existe ;
    sinon None, et l'appelant choisit une reprise adaptée à la raison.
    """

    def __init__(self, raison: str, message: str, jusqua: datetime | None = None):
        super().__init__(message)
        self.raison = raison
        self.message = message
        self.jusqua = jusqua


def prochaine_reinitialisation(maintenant: datetime) -> datetime:
    """Prochain minuit heure du Pacifique, en UTC."""
    local = maintenant.astimezone(PACIFIQUE)
    lendemain = local.date() + timedelta(days=1)
    minuit = datetime(lendemain.year, lendemain.month, lendemain.day, tzinfo=PACIFIQUE)
    return minuit.astimezone(timezone.utc)


def _debut_minute_suivante(maintenant: datetime) -> datetime:
    return maintenant.replace(second=0, microsecond=0) + timedelta(minutes=1)


class SuiviQuota:
    def __init__(
        self,
        redis,
        rpm: int,
        rpd: int,
        tpm: int,
        maintenant: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self._redis = redis
        self._rpm = rpm
        self._rpd = rpd
        self._tpm = tpm
        self._maintenant = maintenant

    def maintenant(self) -> datetime:
        return self._maintenant()

    def _cle_jour(self) -> str:
        jour = self._maintenant().astimezone(PACIFIQUE).date().isoformat()
        return f"gemini:rpd:{jour}"

    def _minute(self) -> int:
        return int(self._maintenant().timestamp() // 60)

    def _lire(self, cle: str) -> int:
        valeur = self._redis.get(cle)
        return int(valeur) if valeur is not None else 0

    def requetes_aujourdhui(self) -> int:
        return self._lire(self._cle_jour())

    def limite_jour_effective(self) -> int:
        return max(self._rpd - RESERVE_JOUR, 0)

    def pause_active(self) -> Pause | None:
        brut = self._redis.get(CLE_PAUSE)
        if brut is None:
            return None
        donnees = json.loads(brut)
        jusqua = datetime.fromisoformat(donnees["jusqua"])
        if jusqua <= self._maintenant():
            self._redis.delete(CLE_PAUSE)
            return None
        return Pause(donnees["raison"], jusqua)

    def poser_pause(self, raison: str, jusqua: datetime) -> None:
        secondes = max(1, math.ceil((jusqua - self._maintenant()).total_seconds()))
        charge = json.dumps({"raison": raison, "jusqua": jusqua.isoformat()})
        self._redis.set(CLE_PAUSE, charge, ex=secondes)

    def autoriser(self, tokens_estimes: int) -> Pause | None:
        """None si la requête peut partir, sinon la pause à appliquer."""
        pause = self.pause_active()
        if pause is not None:
            return pause
        maintenant = self._maintenant()
        if self.requetes_aujourdhui() >= self.limite_jour_effective():
            return Pause(QUOTA_JOUR, prochaine_reinitialisation(maintenant))
        minute = self._minute()
        reprise_minute = _debut_minute_suivante(maintenant)
        if self._lire(f"gemini:rpm:{minute}") >= self._rpm:
            return Pause(QUOTA_MINUTE, reprise_minute)
        if self._lire(f"gemini:tpm:{minute}") + tokens_estimes > self._tpm:
            return Pause(QUOTA_MINUTE, reprise_minute)
        return None

    def _incrementer(self, cle: str, montant: int, ttl: int) -> None:
        # SET NX EX puis INCRBY : la clé naît toujours avec son expiration,
        # sans fenêtre où elle existerait sans TTL.
        self._redis.set(cle, 0, ex=ttl, nx=True)
        self._redis.incrby(cle, montant)

    def enregistrer(self, tokens: int) -> None:
        minute = self._minute()
        self._incrementer(self._cle_jour(), 1, _TTL_JOUR)
        self._incrementer(f"gemini:rpm:{minute}", 1, _TTL_MINUTE)
        self._incrementer(f"gemini:tpm:{minute}", tokens, _TTL_MINUTE)
