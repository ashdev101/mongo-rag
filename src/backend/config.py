"""Configuration settings for the application."""
import os
from pathlib import Path
from dotenv import load_dotenv
from functools import lru_cache

# Load .env from root directory
root_dir = Path(__file__).parent.parent
env_path = root_dir / ".env"
load_dotenv(dotenv_path=env_path)


class Settings:
    """Application configuration settings."""
    
    # Azure AD Configuration
    TENANT_ID: str = os.getenv("TEAMS_APP_TENANT_ID", "9dd4a6f9-b33d-42f5-9128-dd27c439af4b")
    CLIENT_ID: str = os.getenv("AAD_APP_CLIENT_ID", "ba1f97fa-6256-4d54-beff-5b1b711f1dbe")
    AUTHORITY: str = f"https://login.microsoftonline.com/{TENANT_ID}"
    JWKS_URL: str = f"{AUTHORITY}/discovery/v2.0/keys"
    APP_ID_URI: str = os.getenv("APP_ID_URI", f"api://{CLIENT_ID}")

    # Allowed audiences and issuers for token validation
    ALLOWED_AUDIENCES: list = [CLIENT_ID, APP_ID_URI]
    ALLOWED_ISSUERS: list = [
        f"{AUTHORITY}/v2.0",
    ]
    
    # CORS Configuration
    ALLOWED_ORIGINS: list = (
        os.getenv(
            "ALLOWED_ORIGINS",
            "https://localhost:53000"
        ).split(",")
    )
    
    # Server Configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR: str = os.getenv("LOG_DIR", "logs")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "json" if os.getenv("ENVIRONMENT", "development") == "production" else "text")


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
