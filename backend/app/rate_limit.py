from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings

_settings = get_settings()

# Compteur adossé à Redis plutôt qu'à la mémoire du processus : sinon le
# compteur anti-force-brute repart à zéro à chaque redémarrage du conteneur,
# et chaque worker uvicorn tient le sien dans son coin. Redis est déjà une
# dépendance de la stack (file RQ), il n'y a donc pas de service à ajouter.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=f"redis://{_settings.redis_host}:{_settings.redis_port}",
    strategy="fixed-window",
)
