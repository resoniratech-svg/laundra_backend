from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 52560000  # 100 Years = Infinite / Permanent session
    APP_NAME: str = "Laundry SaaS Backend"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    FRONTEND_BASE_URL: str = "http://localhost:5173"
    BACKEND_BASE_URL: str = "http://localhost:8000"
    APPLE_WALLET_WEB_SERVICE_URL: Optional[str] = None

    # Apple Wallet
    APPLE_WALLET_PASS_TYPE_IDENTIFIER: str = "pass.com.resonira.laundry"
    APPLE_WALLET_TEAM_IDENTIFIER: str = "SAMPLE_TEAM_ID"
    APPLE_WALLET_CERTIFICATE_PATH: str = "certificates/apple_wallet/pass.p12"
    APPLE_WALLET_WWDR_CERTIFICATE_PATH: str = "certificates/apple_wallet/AppleWWDRCA.cer"
    APPLE_WALLET_CERTIFICATE_PASSWORD: str = ""
    APPLE_WALLET_TEMPLATE_PATH: str = "templates/apple_wallet/pass.json"
    APPLE_WALLET_ASSETS_PATH: str = "assets/apple_wallet"
    APPLE_WALLET_GENERATED_PATH: str = "generated/apple_wallet"
    APPLE_WALLET_APNS_EXPIRATION_SECONDS: int = 86400
    APPLE_WALLET_APNS_PRIORITY: str = "10"

    # Google Wallet
    GOOGLE_WALLET_ENABLED: bool = True
    GOOGLE_WALLET_ISSUER_ID: Optional[str] = None
    GOOGLE_WALLET_CLASS_SUFFIX: str = "laundra_prepaid_package"
    GOOGLE_WALLET_SERVICE_ACCOUNT_FILE: Optional[str] = "secrets/google-wallet.json"

    @property
    def GOOGLE_WALLET_CLASS_ID(self) -> Optional[str]:
        if self.GOOGLE_WALLET_ISSUER_ID and self.GOOGLE_WALLET_CLASS_SUFFIX:
            return f"{self.GOOGLE_WALLET_ISSUER_ID}.{self.GOOGLE_WALLET_CLASS_SUFFIX}"
        return None

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
