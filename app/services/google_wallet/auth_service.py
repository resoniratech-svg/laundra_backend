import os
import logging
from typing import Optional, Dict, Any
from google.oauth2.service_account import Credentials
from app.core.config import settings

logger = logging.getLogger(__name__)

GOOGLE_WALLET_SCOPES = ["https://www.googleapis.com/auth/wallet_object.issuer"]

class GoogleWalletAuthService:
    @staticmethod
    def get_credentials_path() -> str:
        """
        Resolves path to Google Wallet service account JSON file.
        Searches configured path first, then common workspace fallbacks.
        """
        configured_path = settings.GOOGLE_WALLET_SERVICE_ACCOUNT_FILE or "secrets/google-wallet.json"
        
        candidates = [
            configured_path,
            os.path.abspath(configured_path),
            os.path.join(os.getcwd(), configured_path),
            os.path.join(os.getcwd(), "secrets", "google-wallet.json"),
            os.path.join(os.getcwd(), "laundry-wallet-503005-01c140c9a630.json"),
        ]
        
        for candidate in candidates:
            if candidate and os.path.exists(candidate) and os.path.isfile(candidate):
                return candidate
                
        raise FileNotFoundError(
            f"Google Wallet service account file not found. Checked: {configured_path}"
        )

    @classmethod
    def get_credentials(cls) -> Credentials:
        """
        Loads and returns google-auth Credentials object.
        NO secret fields are logged.
        """
        logger.info("[GoogleWallet] START Authentication")
        
        if not settings.GOOGLE_WALLET_ENABLED:
            logger.warning("[GoogleWallet] FAILURE Authentication | reason=GOOGLE_WALLET_ENABLED is False")
            raise ValueError("Google Wallet integration is disabled in settings.")

        try:
            file_path = cls.get_credentials_path()
            credentials = Credentials.from_service_account_file(
                file_path,
                scopes=GOOGLE_WALLET_SCOPES
            )
            
            project_id = getattr(credentials, "project_id", "unknown")
            service_account_email = getattr(credentials, "service_account_email", "unknown")
            
            logger.info(
                f"[GoogleWallet] SUCCESS Authentication | project_id={project_id} | client_email={service_account_email}"
            )
            return credentials
            
        except Exception as e:
            logger.error(f"[GoogleWallet] FAILURE Authentication | reason={str(e)}")
            raise
