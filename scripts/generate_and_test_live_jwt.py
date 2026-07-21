import json
import jwt
import time
from app.core.config import settings
from app.wallet.auth import get_google_wallet_credentials
from app.wallet.object_service import build_object_payload

def main():
    credentials = get_google_wallet_credentials()
    with open(settings.GOOGLE_WALLET_KEY_PATH, "r", encoding="utf-8") as f:
        key_data = json.load(f)
        private_key = key_data["private_key"]

    # Simple clean generic object
    obj_payload = {
        "id": f"{settings.GOOGLE_WALLET_ISSUER_ID}.customer_live_test_1001",
        "classId": settings.GOOGLE_WALLET_CLASS_ID,
        "state": "ACTIVE",
        "logo": {
            "sourceUri": {
                "uri": "https://raw.githubusercontent.com/google-pay/wallet-samples/main/generic-pass/logo.png"
            },
            "contentDescription": {
                "defaultValue": {
                    "language": "en-US",
                    "value": "Laundra Logo"
                }
            }
        },
        "cardTitle": {
            "defaultValue": {
                "language": "en-US",
                "value": "Laundra Laundry"
            }
        },
        "header": {
            "defaultValue": {
                "language": "en-US",
                "value": "Charan - Prepaid Pass"
            }
        },
        "textModulesData": [
            {
                "id": "balance",
                "header": "BALANCE",
                "body": "QR 50.00"
            }
        ],
        "barcode": {
            "type": "QR_CODE",
            "value": "TEST_TOKEN_1001"
        },
        "hexBackgroundColor": "#1E293B"
    }

    claims = {
        "iss": credentials.service_account_email,
        "aud": "google",
        "origins": [],
        "typ": "savetowallet",
        "iat": int(time.time()),
        "payload": {
            "genericObjects": [obj_payload]
        }
    }

    signed_jwt = jwt.encode(claims, private_key, algorithm="RS256")
    url = f"https://pay.google.com/gp/v/save/{signed_jwt}"
    
    print("=== ULTRA-CLEAN LIVE JWT URL ===")
    print(url)

if __name__ == "__main__":
    main()
