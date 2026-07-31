import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logging
from app.core.config import settings
from app.services.google_wallet import (
    get_google_wallet_client,
    GoogleWalletClassService,
    GoogleWalletObjectService
)

logging.basicConfig(level=logging.INFO)
logger = logger = logging.getLogger(__name__)

def run_phase5_audit():
    print("\n" + "="*60)
    print("   PHASE 5 — GOOGLE WALLET LIVE CLASS & OBJECT AUDIT")
    print("="*60 + "\n")

    client = get_google_wallet_client()
    class_id = GoogleWalletClassService.get_class_id()

    print(f"Issuer ID               : {settings.GOOGLE_WALLET_ISSUER_ID}")
    print(f"Generic Class ID        : {class_id}")
    print(f"Service Account Email   : laundry-wallet-service@laundry-wallet-503005.iam.gserviceaccount.com")

    # 1. Fetch Class from Google REST API
    try:
        class_res = client.genericclass().get(resourceId=class_id).execute()
        print("\n[OK] Generic Class Found on Google API:")
        print(f"  - Class ID            : {class_res.get('id')}")
        print(f"  - Review Status       : {class_res.get('reviewStatus', 'UNDER_REVIEW / UNREVIEWED')}")
        print(f"  - Issuer Name         : {class_res.get('issuerName', 'Laundra Laundry')}")
    except Exception as e:
        print(f"[x] Error Fetching Generic Class: {e}")

    # 2. Fetch Known Working Object from Phase 4
    try:
        # Query DB for recent CustomerPackage with google_wallet_url
        from app.core.database import SessionLocal
        from app.models.customer_package import CustomerPackage
        db = SessionLocal()
        pkg = db.query(CustomerPackage).filter(CustomerPackage.google_wallet_url.isnot(None)).first()
        if pkg:
            obj_id = GoogleWalletObjectService.get_object_id(pkg.id)
            obj_res = client.genericobject().get(resourceId=obj_id).execute()
            print("\n[OK] Generic Object Found on Google API:")
            print(f"  - Object ID           : {obj_res.get('id')}")
            print(f"  - Class ID            : {obj_res.get('classId')}")
            print(f"  - State               : {obj_res.get('state')}")
            print(f"  - Card Title          : {obj_res.get('cardTitle', {}).get('defaultValue', {}).get('value')}")
            print(f"  - Header              : {obj_res.get('header', {}).get('defaultValue', {}).get('value')}")
            print(f"  - Barcode Value       : {obj_res.get('barcode', {}).get('value')}")
            print(f"  - Background Color    : {obj_res.get('hexBackgroundColor')}")
        db.close()
    except Exception as e:
        print(f"[x] Error Fetching Generic Object: {e}")

    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    run_phase5_audit()
