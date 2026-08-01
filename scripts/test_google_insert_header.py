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

def test_insert_header():
    db = SessionLocal()
    try:
        pkg = db.query(CustomerPackage).filter(CustomerPackage.status == "ACTIVE").first()
        cust = db.query(User).filter(User.id == pkg.customer_id).first() if pkg else None
        comp = db.query(Company).filter(Company.id == pkg.tenant_id).first() if pkg else None

        client = get_google_wallet_client()

        print("\n" + "="*60)
        print("  TESTING GOOGLE WALLET OBJECT INSERT WITH HEADER")
        print("="*60)

        # 1. Test INSERT without header (Should FAIL with 'header must be set')
        new_obj_id_1 = f"3388000000023177180.pkg_test_no_header_{uuid.uuid4().hex[:8]}"
        payload_1 = GoogleWalletObjectService.build_generic_object_payload(pkg, cust, comp, object_id=new_obj_id_1)
        
        print(f"\n---> 1. INSERT without 'header' (ID={new_obj_id_1}):")
        try:
            client.genericobject().insert(body=payload_1).execute()
            print("     [x] Unexpectedly Succeeded without header!")
        except Exception as e:
            print(f"     [EXPECTED FAIL 400] Error: {e}")

        # 2. Test INSERT with header set to company_name
        new_obj_id_2 = f"3388000000023177180.pkg_test_with_header_{uuid.uuid4().hex[:8]}"
        payload_2 = dict(payload_1)
        payload_2["id"] = new_obj_id_2
        payload_2["header"] = {
            "defaultValue": {
                "language": "en-US",
                "value": GoogleWalletObjectService.resolve_company_name(comp)
            }
        }
        
        print(f"\n---> 2. INSERT with 'header' = company_name (ID={new_obj_id_2}):")
        try:
            res2 = client.genericobject().insert(body=payload_2).execute()
            print(f"     [SUCCESS] Google Wallet Accepted INSERT! Object ID={res2.get('id')}")
        except Exception as e:
            print(f"     [FAILED] Error: {e}")

    finally:
        db.close()

if __name__ == "__main__":
    test_insert_header()
