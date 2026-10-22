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

    # Filled in later, when we connect Supabase.
    database_url: str | None = None


settings = Settings()
