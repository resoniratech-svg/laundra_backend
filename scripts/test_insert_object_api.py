import json
import uuid
import logging
from app.core.config import settings
from app.wallet.client import get_wallet_client
from app.wallet.object_service import build_object_payload

logging.basicConfig(level=logging.INFO)

def main():
    client = get_wallet_client()
    class_id = settings.GOOGLE_WALLET_CLASS_ID
    object_id = f"{settings.GOOGLE_WALLET_ISSUER_ID}.customer_test_{uuid.uuid4().hex[:8]}"

    obj_payload = build_object_payload(
        customer_package_id="test_pkg_999",
        customer_name="Charan",
        package_name="bulkk",
        remaining_balance=50.0,
        remaining_quantity=20,
        expiry_date_str="2026-08-18",
        status="ACTIVE",
        secure_token="token_999"
    )
    obj_payload["id"] = object_id

    print(f"Attempting to insert object via REST API: {object_id}")
    try:
        res = client.genericobject().insert(body=obj_payload).execute()
        print("SUCCESS! Object Created in Google Wallet API:")
        print(json.dumps(res, indent=2))
    except Exception as e:
        print("API Error inserting object:", e)

if __name__ == "__main__":
    main()
