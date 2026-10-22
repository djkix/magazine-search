"""Limitation de débit des routes d'authentification.

Identification du client
------------------------
Le backend n'est jamais joint directement par le navigateur. La chaîne réelle
est :

    navigateur -> Nginx Proxy Manager -> app-frontend (Next.js) -> app-backend

- NPM ajoute l'adresse du client qu'il voit en fin de X-Forwarded-For
  (`$proxy_add_x_forwarded_for`), APRÈS ce que le client a lui-même envoyé.
- Le proxy de réécriture de Next.js (/api/* -> backend) transmet
  X-Forwarded-For tel quel, SANS y ajouter l'adresse de NPM (vérifié sur
  Next.js 15.5 : sans en-tête entrant, il n'en crée pas non plus).

Le backend reçoit donc « <valeurs fournies par le client>, <IP réelle> », et
la connexion TCP vient du conteneur app-frontend. Seules les N dernières
entrées sont fiables, N étant le nombre de proxys de confiance qui AJOUTENT
une entrée (TRUSTED_PROXY_HOPS, 1 par défaut : NPM). Tout ce qui est plus à
gauche est contrôlé par le client.

uvicorn, avec --proxy-headers et --forwarded-allow-ips="*", retenait au
contraire l'entrée la plus à GAUCHE : un client changeait de compteur à
chaque requête en envoyant un X-Forwarded-For inventé. uvicorn est désormais
lancé avec --no-proxy-headers, et l'adresse est extraite ici.

Ajuster TRUSTED_PROXY_HOPS si la chaîne change : 2 si un second proxy
ajoutant une entrée est placé devant NPM (Cloudflare, par exemple), 0 pour
ignorer X-Forwarded-For (backend joint sans proxy).
"""

import ipaddress

from slowapi import Limiter
from starlette.requests import Request

from app.config import get_settings

_settings = get_settings()


def _normaliser(valeur: str) -> str:
    """Forme canonique d'une adresse IP, pour qu'un même client ne puisse pas
    obtenir plusieurs compteurs en variant l'écriture (zéros, casse IPv6).
    Une valeur qui n'est pas une IP est renvoyée telle quelle : elle provient
    alors d'un proxy de confiance mal configuré, pas du client."""
    try:
        return str(ipaddress.ip_address(valeur))
    except ValueError:
        return valeur


def adresse_client(request: Request, sauts_de_confiance: int | None = None) -> str:
    """Adresse du client telle que vue par le premier proxy de confiance.

    Retient l'entrée de X-Forwarded-For située `sauts_de_confiance` positions
    avant la fin, c'est-à-dire la plus à droite qui n'a pas été écrite par un
    de nos propres proxys. S'il y a moins d'entrées que de sauts, toutes ont
    été écrites par nos proxys et la plus à gauche est la plus proche du
    client. Sans en-tête exploitable, repli sur l'adresse TCP du pair.
    """
    sauts = _settings.trusted_proxy_hops if sauts_de_confiance is None else sauts_de_confiance
    pair = request.client.host if request.client else "inconnu"
    if sauts <= 0:
        return _normaliser(pair)

    # Plusieurs en-têtes X-Forwarded-For valent une seule liste, dans l'ordre
    # (RFC 7230 §3.2.2).
    entrees = [
        morceau.strip()
        for valeur in request.headers.getlist("x-forwarded-for")
        for morceau in valeur.split(",")
        if morceau.strip()
    ]
    if not entrees:
        return _normaliser(pair)
    if len(entrees) >= sauts:
        return _normaliser(entrees[-sauts])
    return _normaliser(entrees[0])


def _storage_uri() -> str:
    return _settings.rate_limit_storage_uri or f"redis://{_settings.redis_host}:{_settings.redis_port}"


# Compteur adossé à Redis plutôt qu'à la mémoire du processus : sinon le
# compteur anti-force-brute repart à zéro à chaque redémarrage du conteneur,
# et chaque worker uvicorn tient le sien dans son coin. Redis est déjà une
# dépendance de la stack (file RQ), il n'y a donc pas de service à ajouter.
limiter = Limiter(
    key_func=adresse_client,
    storage_uri=_storage_uri(),
    strategy="fixed-window",
)
