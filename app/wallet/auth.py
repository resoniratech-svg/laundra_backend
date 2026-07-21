import os
from google.oauth2.service_account import Credentials
from app.core.config import settings

SCOPES = ["https://www.googleapis.com/auth/wallet_object.issuer"]

def get_google_wallet_credentials() -> Credentials:
    """
    Load and return Google OAuth2 Service Account credentials for Google Wallet API.
    """
    key_path = os.path.abspath(settings.GOOGLE_WALLET_KEY_PATH)
    if not os.path.exists(key_path):
        raise FileNotFoundError(f"Google Wallet credentials file not found at: {key_path}")

    credentials = Credentials.from_service_account_file(
        key_path,
        scopes=SCOPES
    )
    return credentials
