from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    APP_NAME: str = "Laundry SaaS Backend"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    GOOGLE_WALLET_ISSUER_ID: str = "338800000023177180"
    GOOGLE_WALLET_CLASS_ID: str = "338800000023177180.laundry_package"
    GOOGLE_WALLET_KEY_PATH: str = "secrets/google-wallet.json"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
