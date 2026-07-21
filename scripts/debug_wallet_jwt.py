import json
import jwt
import time
from app.core.config import settings
from app.wallet.auth import get_google_wallet_credentials
from app.wallet.class_service import get_class_payload
from app.wallet.object_service import build_object_payload

def main():
    credentials = get_google_wallet_credentials()
    with open(settings.GOOGLE_WALLET_KEY_PATH, "r", encoding="utf-8") as f:
        key_data = json.load(f)
        private_key = key_data["private_key"]

    obj = build_object_payload(
        customer_package_id="test_pkg_12345",
        customer_name="Charan",
        package_name="bulkk",
        remaining_balance=50.0,
        remaining_quantity=20,
        expiry_date_str="2026-08-18",
        status="ACTIVE",
        secure_token="test_token_123"
    )

    cls = get_class_payload()

    claims = {
        "iss": credentials.service_account_email,
        "aud": "google",
        "typ": "savetowallet",
        "iat": int(time.time()),
        "payload": {
            "genericClasses": [cls],
            "genericObjects": [obj]
        }
    }

    signed_jwt = jwt.encode(claims, private_key, algorithm="RS256")
    url = f"https://pay.google.com/gp/v/save/{signed_jwt}"
    
    print("--- RAW CLAIMS ---")
    print(json.dumps(claims, indent=2))
    print("\n--- GENERATED SAVE URL ---")
    print(url)

if __name__ == "__main__":
    main()
