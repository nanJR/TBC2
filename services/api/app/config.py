"""App settings, read from environment variables or a local .env file.

Never hard-code keys in Python files. Put them in services/api/.env
(copy .env.example), which git ignores.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Where the front end runs. The browser blocks calls from other sites
    # unless we list them here (this is called CORS).
    frontend_origin: str = "http://localhost:3000"

    # Where the exported models live. See app/inference/registry.py.
    model_dir: str = "models"

    # Secret used to hash ABHA numbers, so the numbers themselves are never stored.
    # Set your own in .env; this default is only for local development.
    abha_hash_key: str = "dev-only-change-me"

    # Supabase (Mumbai). Leave these empty and everything stays in memory, with no login:
    # that's how the tests run, and a fallback if the network fails during a demo.
    # The secret key is a server-only key that bypasses row-level security. Never put it
    # in the front end or in git.
    supabase_url: str | None = None
    supabase_secret_key: str | None = None
    # Ask for a signed-in user (Supabase Auth) on every data request.
    require_login: bool = True

    @property
    def supabase_enabled(self) -> bool:
        return bool(self.supabase_url and self.supabase_secret_key)

    @property
    def login_required(self) -> bool:
        return self.supabase_enabled and self.require_login


settings = Settings()
