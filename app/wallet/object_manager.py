import jwt
import time
import json
import uuid
from typing import Dict, Any, Optional

from app.core.config import settings
from app.wallet.auth import get_google_wallet_credentials
from app.wallet.class_manager import get_generic_class_payload

def build_wallet_object_payload(
    customer_package_id: str,
    customer_name: str,
    package_name: str,
    company_name: str = "Laundra Laundry",
    remaining_balance: float = 0.0,
    remaining_quantity: Optional[int] = 0,
    expiry_date_str: str = "N/A",
    status: str = "ACTIVE",
    secure_token: str = ""
) -> Dict[str, Any]:
    """
    Constructs the Google Wallet Generic Object payload for a specific customer package.
    """
    issuer_id = settings.GOOGLE_WALLET_ISSUER_ID
    class_id = settings.GOOGLE_WALLET_CLASS_ID
    
    # Format clean Object ID: 338800000023177180.cust_pkg_<id>
    clean_id = str(customer_package_id).replace("-", "")
    object_id = f"{issuer_id}.pkg_{clean_id}"

    balance_display = f"QR {remaining_balance:.2f}" if remaining_balance > 0 else f"{remaining_quantity or 0} Items"
    quantity_display = f"{remaining_quantity} items left" if remaining_quantity is not None else "Unlimited"

    return {
        "id": object_id,
        "classId": class_id,
        "state": "ACTIVE" if status.upper() == "ACTIVE" else "EXPIRED",
        "cardTitle": {
            "defaultValue": {
                "language": "en-US",
                "value": company_name
            }
        },
        "header": {
            "defaultValue": {
                "language": "en-US",
                "value": f"{customer_name} - {package_name}"
            }
        },
        "textModulesData": [
            {
                "id": "balance",
                "header": "BALANCE",
                "body": balance_display
            },
            {
                "id": "remaining_orders",
                "header": "ITEMS REMAINING",
                "body": quantity_display
            },
            {
                "id": "expiry_date",
                "header": "EXPIRY DATE",
                "body": expiry_date_str
            },
            {
                "id": "status",
                "header": "STATUS",
                "body": status.upper()
            }
        ],
        "barcode": {
            "type": "QR_CODE",
            "value": secure_token or str(customer_package_id),
            "alternateText": secure_token[:12] if secure_token else str(customer_package_id)[:12]
        },
        "hexBackgroundColor": "#1E293B"
    }

def generate_google_wallet_save_url(wallet_object: Dict[str, Any]) -> str:
    """
    Signs a JWT containing the Generic Class and Generic Object,
    returning the official 'Add to Google Wallet' URL.
    """
    credentials = get_google_wallet_credentials()
    
    # Read service account private key from JSON
    with open(settings.GOOGLE_WALLET_KEY_PATH, "r", encoding="utf-8") as f:
        key_data = json.load(f)
        private_key = key_data["private_key"]

    now = int(time.time())
    payload_claims = {
        "iss": credentials.service_account_email,
        "aud": "google",
        "origins": ["http://localhost:5173", "http://127.0.0.1:5173", "https://laundra.app", settings.FRONTEND_BASE_URL],
        "typ": "savetowallet",
        "iat": now,
        "payload": {
            "genericClasses": [get_generic_class_payload()],
            "genericObjects": [wallet_object]
        }
    }

    # Sign JWT with RS256 algorithm using service account private key
    signed_jwt = jwt.encode(payload_claims, private_key, algorithm="RS256")
    
    # Return official Google Wallet save link
    return f"https://pay.google.com/gp/v/save/{signed_jwt}"

if __name__ == "__main__":
    test_object = build_wallet_object_payload(
        customer_package_id="1001-pkg-demo",
        customer_name="Ahmed",
        package_name="Premium Package",
        company_name="Laundra HQ",
        remaining_balance=425.0,
        remaining_quantity=17,
        expiry_date_str="2027-07-20",
        status="ACTIVE",
        secure_token="DEMO-SECURE-TOKEN-12345"
    )
    save_url = generate_google_wallet_save_url(test_object)
    print("[SUCCESS] Google Wallet Object & Save URL Created!")
    print(f"   Object ID  : {test_object['id']}")
    print(f"   Save URL   : {save_url[:65]}...")

