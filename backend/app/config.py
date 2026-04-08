from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database — SQLite for local dev (no Docker needed), PostgreSQL for prod
    database_url: str = "sqlite+aiosqlite:///./meld.db"

    # Anthropic
    anthropic_api_key: str = ""

    # Oura
    oura_client_id: str = ""
    oura_client_secret: str = ""
    oura_redirect_uri: str = "http://localhost:8000/api/auth/oura/callback"

    # App
    app_env: str = "development"
    app_secret_key: str = "change-me"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
