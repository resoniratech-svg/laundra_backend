import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logging
from app.core.database import SessionLocal
from app.models.customer_package import CustomerPackage
from app.models.user import User
from app.models.company import Company
from app.services.google_wallet import (
    get_google_wallet_client,
    GoogleWalletClassService,
    GoogleWalletObjectService
)

logging.basicConfig(level=logging.INFO)

def test_header_values():
    db = SessionLocal()
    try:
        pkg = db.query(CustomerPackage).filter(CustomerPackage.status == "ACTIVE").first()
        cust = db.query(User).filter(User.id == pkg.customer_id).first() if pkg else None
        comp = db.query(Company).filter(Company.id == pkg.tenant_id).first() if pkg else None

        if not pkg:
            print("[x] No CustomerPackage found to test.")
            return

        client = get_google_wallet_client()

        print("\n" + "="*60)
        print("  TESTING GOOGLE WALLET OBJECT HEADER VALIDATION")
        print("="*60)

        # Base payload without header
        base_payload = GoogleWalletObjectService.build_generic_object_payload(pkg, cust, comp)
        
        test_headers = [
            ("MISSING (None)", None),
            ("EMPTY STRING ('')", ""),
            ("SINGLE SPACE (' ')", " "),
            ("NBSP ('\u00A0')", "\u00A0"),
            ("COMPANY NAME", GoogleWalletObjectService.resolve_company_name(comp)),
            ("CUSTOMER NAME", GoogleWalletObjectService.resolve_customer_name(cust)),
            ("PREPAID PASS", "Prepaid Pass")
        ]

        for label, val in test_headers:
            payload = dict(base_payload)
            if val is None:
                payload.pop("header", None)
            else:
                payload["header"] = {
                    "defaultValue": {
                        "language": "en-US",
                        "value": val
                    }
                }

            obj_id = payload["id"]
            print(f"\n---> Testing Header Value: [{label}] -> '{val}'")
            try:
                res = client.genericobject().patch(resourceId=obj_id, body=payload).execute()
                print(f"     [SUCCESS] Google Wallet API Accepted Header! Object ID={res.get('id')}")
            except Exception as e:
                print(f"     [FAILED] Google Wallet API Error: {e}")

    finally:
        db.close()

if __name__ == "__main__":
    test_header_values()
