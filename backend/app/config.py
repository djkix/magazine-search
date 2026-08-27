from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://magazines:magazines@localhost:5432/magazines"

    redis_host: str = "localhost"
    redis_port: int = 6379

    meili_host: str = "http://localhost:7700"
    meili_master_key: str = ""
    meili_index_pages: str = "pages"

    jwt_secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    backend_cors_origins: str = ""

    admin_bootstrap_email: str = ""
    admin_bootstrap_password: str = ""

    nas_mount_path: str = "/mnt/nas"
    covers_dir: str = "/data/covers"
    processed_dir: str = "/data/processed"

    login_rate_limit: str = "5/15minutes"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.backend_cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
