import jwt
import time
import json
import logging
from typing import Dict, Any

from app.core.config import settings
from app.wallet.auth import get_google_wallet_credentials
from app.wallet.class_service import get_class_payload
from app.wallet.exceptions import WalletJWTError

logger = logging.getLogger("google_wallet")

def generate_add_to_wallet_url(wallet_object_payload: Dict[str, Any]) -> str:
    """
    Generates the signed Google Wallet JWT and logs '[INFO] JWT Generated'.
    """
    try:
        credentials = get_google_wallet_credentials()
        
        with open(settings.GOOGLE_WALLET_KEY_PATH, "r", encoding="utf-8") as f:
            key_data = json.load(f)
            private_key = key_data["private_key"]

        now = int(time.time())
        claims = {
            "iss": credentials.service_account_email,
            "aud": "google",
            "origins": [],
            "typ": "savetowallet",
            "iat": now,
            "payload": {
                "genericClasses": [get_class_payload()],
                "genericObjects": [wallet_object_payload]
            }
        }

        signed_jwt = jwt.encode(claims, private_key, algorithm="RS256")
        logger.info(f"[INFO] JWT Generated for Object ID: {wallet_object_payload.get('id')}")
        
        return f"https://pay.google.com/gp/v/save/{signed_jwt}"
    except Exception as e:
        logger.error(f"[ERROR] JWT Generation Failed: {e}")
        raise WalletJWTError(f"Failed to generate Add to Google Wallet URL: {e}")
