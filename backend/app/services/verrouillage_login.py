"""Verrouillage temporaire d'un compte après des échecs de connexion répétés.

La limite par adresse IP (app/rate_limit.py) n'arrête pas une attaque
répartie sur de nombreuses adresses. Ce compteur-ci est tenu par EMAIL visé,
quelle que soit l'origine des tentatives : au-delà du seuil, l'email est
refusé pendant la durée du verrou, même avec le bon mot de passe.

Le compteur s'applique aussi aux emails inexistants, sans quoi le verrou
révélerait quels comptes existent. L'email n'est pas stocké en clair dans
Redis : seule son empreinte SHA-256 sert de clé.

Revers assumé : un tiers peut verrouiller un compte en enchaînant les échecs.
Le verrou est court (15 min par défaut) et n'empêche pas la connexion Google
d'un compte rattaché.
"""

import hashlib

import redis

from app.config import get_settings

_PREFIXE_ECHECS = "login:echecs:"
_PREFIXE_VERROU = "login:verrou:"


def _empreinte(identifiant: str) -> str:
    return hashlib.sha256(identifiant.strip().lower().encode()).hexdigest()


class VerrouillageCompte:
    def __init__(self, client_redis, max_echecs: int, fenetre_secondes: int, duree_verrou_secondes: int):
        self.redis = client_redis
        self.max_echecs = max_echecs
        self.fenetre_secondes = fenetre_secondes
        self.duree_verrou_secondes = duree_verrou_secondes

    def secondes_restantes(self, identifiant: str) -> int:
        """Durée restante du verrou en secondes, 0 si le compte est libre."""
        if self.max_echecs <= 0:
            return 0
        ttl = self.redis.ttl(_PREFIXE_VERROU + _empreinte(identifiant))
        return max(int(ttl), 0) if ttl is not None and ttl > 0 else 0

    def enregistrer_echec(self, identifiant: str) -> bool:
        """Compte un échec ; renvoie True si le compte vient d'être verrouillé."""
        if self.max_echecs <= 0:
            return False
        empreinte = _empreinte(identifiant)
        cle = _PREFIXE_ECHECS + empreinte
        echecs = self.redis.incr(cle)
        if echecs == 1:
            # La fenêtre part du premier échec : fenêtre fixe, comme la
            # limite par IP.
            self.redis.expire(cle, self.fenetre_secondes)
        if echecs >= self.max_echecs:
            self.redis.set(_PREFIXE_VERROU + empreinte, 1, ex=self.duree_verrou_secondes)
            self.redis.delete(cle)
            return True
        return False

    def reinitialiser(self, identifiant: str) -> None:
        """Après une connexion réussie : les échecs précédents sont oubliés."""
        self.redis.delete(_PREFIXE_ECHECS + _empreinte(identifiant))


_instance: VerrouillageCompte | None = None


def get_verrouillage() -> VerrouillageCompte:
    """Dépendance FastAPI ; remplacée par un faux Redis dans les tests."""
    global _instance
    if _instance is None:
        settings = get_settings()
        _instance = VerrouillageCompte(
            redis.Redis(host=settings.redis_host, port=settings.redis_port),
            max_echecs=settings.login_lockout_max_failures,
            fenetre_secondes=settings.login_lockout_window_minutes * 60,
            duree_verrou_secondes=settings.login_lockout_minutes * 60,
        )
    return _instance
