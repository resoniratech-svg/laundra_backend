import json
import time
import logging
import jwt
from typing import Dict, Any, Optional
from app.services.google_wallet.auth_service import GoogleWalletAuthService

logger = logging.getLogger(__name__)

class GoogleWalletJwtService:
    @classmethod
    def generate_save_url(cls, object_payload: Dict[str, Any], class_payload: Optional[Dict[str, Any]] = None) -> str:
        """
        Generates Google's signed 'Add to Google Wallet' JWT URL.
        NO private keys or signed JWT tokens are printed to logs.
        """
        logger.info(f"[GoogleWallet] START JWT Signing | object_id={object_payload.get('id')}")

        try:
            cred_path = GoogleWalletAuthService.get_credentials_path()
            with open(cred_path, "r", encoding="utf-8") as f:
                key_data = json.load(f)
                private_key = key_data.get("private_key")
                client_email = key_data.get("client_email")

            if not private_key or not client_email:
                raise ValueError("Service account JSON file missing private_key or client_email.")

            payload_data: Dict[str, Any] = {
                "genericObjects": [object_payload]
            }
            if class_payload:
                payload_data["genericClasses"] = [class_payload]

            claims = {
                "iss": client_email,
                "aud": "google",
                "origins": [],
                "typ": "savetowallet",
                "iat": int(time.time()),
                "payload": payload_data
            }

            # Sign JWT using RS256 algorithm
            signed_jwt = jwt.encode(claims, private_key, algorithm="RS256")

            # Handle pyjwt string/bytes compatibility
            if isinstance(signed_jwt, bytes):
                signed_jwt = signed_jwt.decode("utf-8")

            save_url = f"https://pay.google.com/gp/v/save/{signed_jwt}"
            
            logger.info(f"[GoogleWallet] SUCCESS JWT Signing | object_id={object_payload.get('id')}")
            return save_url

        except Exception as e:
            logger.error(f"[GoogleWallet] FAILURE JWT Signing | reason={str(e)}")
            raise
