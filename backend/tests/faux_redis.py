"""Redis minimal en mémoire, avec expiration pilotée par une horloge injectée."""

import math
from datetime import datetime, timezone


class Horloge:
    """Horloge modifiable : `horloge.maintenant = ...` fait avancer le temps."""

    def __init__(self, maintenant: datetime | None = None):
        self.maintenant = maintenant or datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.maintenant


class FauxRedis:
    def __init__(self, horloge: Horloge | None = None):
        self.horloge = horloge or Horloge()
        self._valeurs: dict[str, bytes] = {}
        self._echeances: dict[str, datetime] = {}

    def _purger(self, nom: str) -> None:
        echeance = self._echeances.get(nom)
        if echeance is not None and echeance <= self.horloge():
            self._valeurs.pop(nom, None)
            self._echeances.pop(nom, None)

    def get(self, nom):
        self._purger(nom)
        return self._valeurs.get(nom)

    def set(self, nom, valeur, ex=None, nx=False):
        self._purger(nom)
        if nx and nom in self._valeurs:
            return None
        self._valeurs[nom] = str(valeur).encode()
        self._echeances.pop(nom, None)
        if ex is not None:
            self.expire(nom, ex)
        return True

    def incrby(self, nom, montant=1):
        self._purger(nom)
        valeur = int(self._valeurs.get(nom, b"0")) + montant
        self._valeurs[nom] = str(valeur).encode()
        return valeur

    def incr(self, nom):
        return self.incrby(nom, 1)

    def expire(self, nom, secondes):
        from datetime import timedelta

        if nom in self._valeurs:
            self._echeances[nom] = self.horloge() + timedelta(seconds=secondes)
        return True

    def delete(self, nom):
        self._valeurs.pop(nom, None)
        self._echeances.pop(nom, None)

    def ttl(self, nom):
        self._purger(nom)
        if nom not in self._valeurs:
            return -2
        echeance = self._echeances.get(nom)
        if echeance is None:
            return -1
        return math.ceil((echeance - self.horloge()).total_seconds())
