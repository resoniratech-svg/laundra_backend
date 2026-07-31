import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logging
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.company import Company
from app.models.user import User
from app.models.prepaid_package import PrepaidPackage
from app.models.customer_package import CustomerPackage
from app.services.google_wallet import (
    GoogleWalletAuthService,
    get_google_wallet_client,
    GoogleWalletObjectService
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_design_update():
    summary = {
        "customer_package": "FAIL",
        "google_object": "FAIL",
        "company_name": "N/A",
        "package_name": "N/A",
        "customer_name": "N/A",
        "remaining_balance": "N/A",
        "valid_until": "N/A",
        "services": "N/A",
        "qr": "FAIL",
        "background": "N/A",
        "object_update": "FAIL",
        "object_fetch": "FAIL",
        "final_result": "FAIL"
    }

    print("\n" + "="*60)
    print("   GOOGLE WALLET CARD DESIGN REFINEMENT (PHASE 2.5)")
    print("="*60 + "\n")

    db = SessionLocal()

    try:
        # 1. Load active CustomerPackage from DB
        test_pkg = db.query(CustomerPackage).filter(CustomerPackage.status == "ACTIVE").order_by(CustomerPackage.purchase_date.desc()).first()
        if not test_pkg:
            print("[x] Error: No active CustomerPackage found in DB.")
            return print_summary(summary)

        summary["customer_package"] = f"FOUND (ID: {str(test_pkg.id)[:8]}...)"
        
        customer = db.query(User).filter(User.id == test_pkg.customer_id).first()
        company = db.query(Company).filter(Company.id == test_pkg.tenant_id).first()

        # 2. Extract resolved fields
        comp_name = GoogleWalletObjectService.resolve_company_name(company)
        pkg_name = GoogleWalletObjectService.resolve_package_name(test_pkg)
        cust_name = GoogleWalletObjectService.resolve_customer_name(customer)
        bal_val = float(test_pkg.current_balance or test_pkg.package_value or 0.0)
        expiry_formatted = GoogleWalletObjectService.format_expiry_date(test_pkg.expiry_date)
        services_formatted = GoogleWalletObjectService.format_services_summary(test_pkg)
        bg_hex = GoogleWalletObjectService.resolve_background_color(test_pkg)

        summary["company_name"] = comp_name
        summary["package_name"] = pkg_name
        summary["customer_name"] = cust_name
        summary["remaining_balance"] = f"QR {bal_val:.2f}"
        summary["valid_until"] = expiry_formatted
        summary["services"] = services_formatted
        summary["background"] = bg_hex
        summary["qr"] = "CONFIGURED" if test_pkg.secure_token else "FALLBACK"

        # 3. Patch live object in Google Wallet API
        client = get_google_wallet_client()
        patch_res = GoogleWalletObjectService.patch_generic_object(
            package=test_pkg,
            customer=customer,
            company=company,
            client=client
        )
        summary["object_update"] = "PASS"
        summary["google_object"] = f"FOUND ({patch_res['object_id']})"
        print(f"[OK] Live GenericObject Patched: Object ID={patch_res['object_id']}")

        # 4. Fetch updated object back from Google Wallet API
        fetched_obj = GoogleWalletObjectService.get_generic_object(
            object_id=patch_res['object_id'],
            client=client
        )
        assert fetched_obj.get("id") == patch_res['object_id'], "Fetched object ID mismatch"
        summary["object_fetch"] = "PASS"
        summary["final_result"] = "PASS"
        print(f"[OK] Live Object Fetched Back Successfully. State={fetched_obj.get('state')}")

        print_summary(summary)

    except Exception as e:
        logger.exception(f"[x] Design Verification Error: {e}")
        print(f"[x] Error: {e}")
        print_summary(summary)
    finally:
        db.close()

def print_summary(s: dict):
    print("\n" + "="*60)
    print("GOOGLE WALLET DESIGN VERIFICATION")
    print("="*60)
    print(f"Customer Package     : {s['customer_package']}")
    print(f"Google Object        : {s['google_object']}")
    print(f"Company Name         : {s['company_name']}")
    print(f"Package Name         : {s['package_name']}")
    print(f"Customer Name        : {s['customer_name']}")
    print(f"Remaining Balance    : {s['remaining_balance']}")
    print(f"Valid Until          : {s['valid_until']}")
    print(f"Services             : {s['services']}")
    print(f"QR Code              : {s['qr']}")
    print(f"Background Color     : {s['background']}")
    print(f"Object Update        : {s['object_update']}")
    print(f"Object Fetch         : {s['object_fetch']}")
    print(f"Final Result         : {s['final_result']}")
    print("="*60 + "\n")

if __name__ == "__main__":
    test_design_update()
