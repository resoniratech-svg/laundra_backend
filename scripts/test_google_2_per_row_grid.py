import os
import sys
import uuid
import datetime

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logging
from app.core.database import SessionLocal
from app.models.customer_package import CustomerPackage
from app.models.user import User
from app.models.company import Company
from app.models.prepaid_package import PrepaidPackage
from app.services.google_wallet import (
    get_google_wallet_client,
    GoogleWalletClassService,
    GoogleWalletObjectService
)

logging.basicConfig(level=logging.INFO)

def test_2_per_row_grid():
    db = SessionLocal()
    try:
        customer = db.query(User).filter(User.name.isnot(None)).first()
        company = db.query(Company).first()
        pkg_def = db.query(PrepaidPackage).first()

        assert customer is not None, "Customer not found"
        assert company is not None, "Company not found"
        pkg_id = pkg_def.id if pkg_def else uuid.uuid4()

        client = get_google_wallet_client()

        print("\n" + "="*70)
        print("  TESTING 2 SERVICES PER ROW GRID LAYOUT & OFFER PRICE")
        print("="*70)

        # 1. Test Package with 6 Services & Offer Price (Original QR 350, Offer QR 294)
        pkg_6 = CustomerPackage(
            id=uuid.uuid4(),
            tenant_id=company.id,
            customer_id=customer.id,
            package_id=pkg_id,
            purchase_date=datetime.datetime.utcnow(),
            total_quantity=35,
            package_value=350.00,
            current_balance=294.00,
            used_amount=0.0,
            status="ACTIVE",
            secure_token=str(uuid.uuid4()),
            pass_color="GOLD",
            service_items=[
                {"service": "Pressing", "total": 7, "left": 7},
                {"service": "Wash & Press", "total": 6, "left": 6},
                {"service": "Dry Cleaning", "total": 6, "left": 6},
                {"service": "Premium Services", "total": 5, "left": 5},
                {"service": "Wash & Fold", "total": 5, "left": 5},
                {"service": "Commercial Laundry", "total": 6, "left": 6}
            ]
        )

        # Attach PrepaidPackage relation with offer_price = 294.00 and original_price = 350.00
        if pkg_def:
            pkg_def.original_price = 350.00
            pkg_def.offer_price = 294.00
            pkg_6.package = pkg_def

        db.add(pkg_6)
        db.commit()
        db.refresh(pkg_6)

        # Build payload
        payload = GoogleWalletObjectService.build_generic_object_payload(pkg_6, customer, company)

        # Verify Coupon Cost displays OFFER PRICE (QR 294.00)
        coupon_cost_module = next((m for m in payload["textModulesData"] if m["id"] == "coupon_cost"), None)
        assert coupon_cost_module is not None, "coupon_cost module not found"
        coupon_cost_body = coupon_cost_module["body"]
        print(f"\n[+] Verified COUPON COST field: '{coupon_cost_body}'")
        assert coupon_cost_body == "QR 294.00", f"Expected 'QR 294.00', got '{coupon_cost_body}'"
        print("[OK] COUPON COST displays OFFER PRICE (QR 294.00) PASS!")

        # Verify Text Modules generated for 6 services
        srv_modules = [m for m in payload["textModulesData"] if m["id"].startswith("service_")]
        print(f"\n[+] Generated {len(srv_modules)} service text modules:")
        for sm in srv_modules:
            print(f"    - {sm['id']}: Header='{sm['header']}' | Body='{sm['body']}'")

        assert len(srv_modules) == 6, f"Expected 6 service modules, got {len(srv_modules)}"

        # Cleanup test package
        db.delete(pkg_6)
        db.commit()

        print("\n" + "="*70)
        print("  ALL GRID & OFFER PRICE CHECKS PASSED 100%")
        print("="*70 + "\n")

    finally:
        db.close()

if __name__ == "__main__":
    test_2_per_row_grid()
