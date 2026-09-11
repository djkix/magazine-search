from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valeurs proposées par le `.env.example` ou héritées d'anciennes versions.
# Elles sont publiques : les accepter au démarrage reviendrait à signer les
# jetons avec un secret que n'importe quel lecteur du dépôt connaît.
_SECRETS_INTERDITS = {
    "changeme",
    "change-me",
    "dev-secret-change-me",
    "changeme-generate-a-long-random-secret",
    "changeme-generate-a-long-random-key",
    "__REMPLACER__",
    "secret",
    "password",
}

_LONGUEUR_SECRET_MIN = 32


def _rejeter_secret_faible(valeur: str, nom: str, longueur_min: int) -> str:
    """Refuse une valeur vide, connue publiquement ou trop courte."""
    valeur = valeur.strip()
    if not valeur:
        raise ValueError(f"{nom} est obligatoire et ne doit pas être vide.")
    if valeur.lower() in _SECRETS_INTERDITS:
        raise ValueError(
            f"{nom} utilise une valeur par défaut connue publiquement. "
            "Générez-en une nouvelle, par exemple avec « openssl rand -hex 32 »."
        )
    if len(valeur) < longueur_min:
        raise ValueError(
            f"{nom} doit faire au moins {longueur_min} caractères (actuellement {len(valeur)})."
        )
    return valeur


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://magazines:magazines@localhost:5432/magazines"

    redis_host: str = "localhost"
    redis_port: int = 6379

    # Borne des appels HTTP vers Meilisearch. Sans elle, une indexation part
    # sur le timeout par défaut de la librairie (très long, voire aucun) et
    # peut immobiliser l'unique worker.
    meili_timeout_seconds: int = 15

    meili_host: str = "http://localhost:7700"
    # Sans valeur de repli : l'application refuse de démarrer si la variable
    # d'environnement est absente, plutôt que de tourner sans protection.
    meili_master_key: str
    meili_index_pages: str = "pages"

    jwt_secret_key: str
    # jwt_algorithm a été retiré volontairement : l'algorithme est désormais
    # figé dans app/security.py (JWT_ALGORITHM). Le laisser configurable
    # permettait d'affaiblir la signature depuis l'environnement.
    jwt_expire_minutes: int = 1440

    backend_cors_origins: str = ""

    # /docs, /redoc et /openapi.json cartographient toute la surface d'API.
    # Fermés par défaut : à n'activer qu'en développement local.
    enable_api_docs: bool = False

    # Le compte d'amorçage reste facultatif : laissé vide, aucun compte n'est
    # créé. Mais s'il est renseigné, le mot de passe doit être sérieux.
    admin_bootstrap_email: str = ""
    admin_bootstrap_password: str = ""

    @field_validator("jwt_secret_key")
    @classmethod
    def _valider_jwt_secret(cls, v: str) -> str:
        return _rejeter_secret_faible(v, "JWT_SECRET_KEY", _LONGUEUR_SECRET_MIN)

    @field_validator("meili_master_key")
    @classmethod
    def _valider_meili_key(cls, v: str) -> str:
        return _rejeter_secret_faible(v, "MEILI_MASTER_KEY", 16)

    @field_validator("admin_bootstrap_password")
    @classmethod
    def _valider_mdp_bootstrap(cls, v: str) -> str:
        if not v:
            return v
        return _rejeter_secret_faible(v, "ADMIN_BOOTSTRAP_PASSWORD", 12)

    # Borne du sous-processus ocrmypdf. Tenue sous le job_timeout RQ (30 min)
    # pour que l'échec soit signalé sur le numéro plutôt que par la mort du job.
    ocr_timeout_seconds: int = 1500

    nas_mount_path: str = "/mnt/nas"
    covers_dir: str = "/data/covers"
    processed_dir: str = "/data/processed"

    login_rate_limit: str = "5/15minutes"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    # Borne des appels a l'API Gemini. C'etait le dernier appel reseau sans
    # limite du systeme : une connexion suspendue immobilisait l'unique worker
    # jusqu'au job_timeout RQ de 15 minutes, et recommencait a chaque essai.
    #
    # Exprime en secondes ici, converti en millisecondes a l'appel : le SDK
    # attend des millisecondes, unite trop facile a confondre dans un .env.
    #
    # 120 s est large — un lot de 20 numeros produit environ 190 jetons de
    # sortie chacun, soit quelques secondes en regime normal. Au-dela, la
    # connexion est suspendue, pas lente.
    gemini_timeout_seconds: int = 120

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.backend_cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
