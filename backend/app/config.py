import os
from pathlib import Path
from pydantic_settings import BaseSettings

# Manually load .env since pydantic-settings has issues on Python 3.14
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
if ENV_FILE.exists():
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite+aiosqlite:///./meld.db"

    # Anthropic
    anthropic_api_key: str = ""

    # Oura
    oura_client_id: str = ""
    oura_client_secret: str = ""
    oura_redirect_uri: str = "http://localhost:8000/auth/oura/callback"

    # App
    app_env: str = "development"
    app_secret_key: str = "change-me"


settings = Settings()
