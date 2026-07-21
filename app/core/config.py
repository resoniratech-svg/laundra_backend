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

    # Apple Wallet
    APPLE_WALLET_PASS_TYPE_IDENTIFIER: str = "pass.com.resonira.laundry"
    APPLE_WALLET_TEAM_IDENTIFIER: str = "SAMPLE_TEAM_ID"
    APPLE_WALLET_CERTIFICATE_PATH: str = "certificates/apple_wallet/pass.p12"
    APPLE_WALLET_WWDR_CERTIFICATE_PATH: str = "certificates/apple_wallet/AppleWWDRCA.cer"
    APPLE_WALLET_CERTIFICATE_PASSWORD: str = ""
    APPLE_WALLET_TEMPLATE_PATH: str = "templates/apple_wallet/pass.json"
    APPLE_WALLET_ASSETS_PATH: str = "assets/apple_wallet"
    APPLE_WALLET_GENERATED_PATH: str = "generated/apple_wallet"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
