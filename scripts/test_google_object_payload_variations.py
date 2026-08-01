import os
import sys
import uuid

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logging
from app.core.database import SessionLocal
from app.models.customer_package import CustomerPackage
from app.models.user import User
from app.models.company import Company
from app.services.google_wallet import (
    get_google_wallet_client,
    GoogleWalletObjectService
)

logging.basicConfig(level=logging.INFO)

def test_payload_variations():
    db = SessionLocal()
    try:
        pkg = db.query(CustomerPackage).filter(CustomerPackage.status == "ACTIVE").first()
        cust = db.query(User).filter(User.id == pkg.customer_id).first() if pkg else None
        comp = db.query(Company).filter(Company.id == pkg.tenant_id).first() if pkg else None

        client = get_google_wallet_client()

        print("\n" + "="*60)
        print("  TESTING GOOGLE WALLET PAYLOAD VARIATIONS FOR EXACT UI MATCH")
        print("="*60)

        # Build base payload
        base_payload = GoogleWalletObjectService.build_generic_object_payload(pkg, cust, comp)
        
        print("\n--- Current Base Payload Structure ---")
        print(f"CardTitle: {base_payload.get('cardTitle')}")
        print(f"Header   : {base_payload.get('header')}")
        print(f"TextModules count: {len(base_payload.get('textModulesData', []))}")
        for m in base_payload.get('textModulesData', []):
            print(f"  - ID: {m.get('id'):15s} | Header: {m.get('header'):20s} | Body: {m.get('body')}")

        # Test setting header = customer_name
        test_obj_id = f"3388000000023177180.pkg_test_ui_{uuid.uuid4().hex[:8]}"
        payload_test = dict(base_payload)
        payload_test["id"] = test_obj_id
        payload_test["header"] = {
            "defaultValue": {
                "language": "en-US",
                "value": GoogleWalletObjectService.resolve_customer_name(cust)
            }
        }

        print(f"\n---> Testing Object Creation with header = customer_name ('{GoogleWalletObjectService.resolve_customer_name(cust)}')")
        try:
            res = client.genericobject().insert(body=payload_test).execute()
            print(f"     [SUCCESS] Object Created! ID={res.get('id')}")
            print(f"     Save URL: https://pay.google.com/gp/v/save/[REDACTED]")
        except Exception as e:
            print(f"     [FAIL] Error: {e}")

    finally:
        db.close()

if __name__ == "__main__":
    test_payload_variations()
