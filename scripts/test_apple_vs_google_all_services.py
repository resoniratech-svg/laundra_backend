import os
import sys
import uuid
import datetime
import json

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logging
from app.core.database import SessionLocal
from app.models.customer_package import CustomerPackage
from app.models.user import User
from app.models.company import Company
from app.models.prepaid_package import PrepaidPackage
from app.services.google_wallet import GoogleWalletObjectService
from app.services.apple_wallet.pass_service import PassService as ApplePassService, LaundryPassData

logging.basicConfig(level=logging.INFO)

def test_apple_vs_google_services():
    db = SessionLocal()
    try:
        customer = db.query(User).filter(User.name.isnot(None)).first()
        company = db.query(Company).first()
        pkg_def = db.query(PrepaidPackage).first()

        assert customer is not None, "Customer not found"
        assert company is not None, "Company not found"
        pkg_id = pkg_def.id if pkg_def else uuid.uuid4()

        print("\n" + "="*75)
        print("  VERIFYING APPLE WALLET VS GOOGLE WALLET DYNAMIC ALL SERVICES DISPLAY")
        print("="*75)

        test_service_counts = [1, 2, 3, 5, 8, 10]
        service_pool = [
            "Pressing", "Wash & Press", "Dry Cleaning", "Premium Services",
            "Wash & Fold", "Commercial Laundry", "Steam Press", "Hotel Laundry",
            "Curtains", "Carpet Clean"
        ]

        apple_service = ApplePassService()

        for count in test_service_counts:
            items = [{"service": service_pool[i], "total": 10, "left": 10} for i in range(count)]
            pkg = CustomerPackage(
                id=uuid.uuid4(),
                tenant_id=company.id,
                customer_id=customer.id,
                package_id=pkg_id,
                purchase_date=datetime.datetime.utcnow(),
                total_quantity=10 * count,
                package_value=100.0,
                current_balance=100.0,
                status="ACTIVE",
                secure_token=str(uuid.uuid4()),
                service_items=items
            )

            # 1. Google Wallet Payload
            gw_payload = GoogleWalletObjectService.build_generic_object_payload(pkg, customer, company)
            gw_srv_modules = [m for m in gw_payload["textModulesData"] if m["id"].startswith("service_")]

            # 2. Apple Wallet Pass JSON Structure
            pass_data = LaundryPassData(
                company_name=company.name,
                customer_name=customer.name,
                package_name="LUXURY PACKAGE",
                package_id=str(pkg.id),
                remaining_balance="100.00",
                expiry_date="31 Aug 2026",
                qr_data="https://example.com/qr",
                service_items=items
            )

            pass_json_path = apple_service.generate(pass_data, serial_number=f"TEST-{pkg.id}")
            with open(pass_json_path, "r", encoding="utf-8") as f:
                apple_pass_dict = json.load(f)

            generic = apple_pass_dict.get("generic", {})
            aux_fields = generic.get("auxiliaryFields", [])
            back_fields = generic.get("backFields", [])

            print(f"\n[+] Package with {count:2d} Assigned Services:")
            print(f"    - Google Wallet Modules Count: {len(gw_srv_modules)}")
            print(f"    - Apple Wallet Aux Fields    : {len(aux_fields)}")
            print(f"    - Apple Wallet Back Fields   : {len(back_fields)}")

            assert len(gw_srv_modules) == count, f"Google Wallet missing services! Expected {count}, got {len(gw_srv_modules)}"
            assert len(aux_fields) == count, f"Apple Wallet front auxiliaryFields missing services! Expected {count}, got {len(aux_fields)}"
            
            # Check that all services are present in Apple Wallet backFields
            back_labels = [bf["label"] for bf in back_fields]
            for itm in items:
                expected_label = f"{itm['service'].upper()} LEFT"
                assert expected_label in back_labels, f"Service '{expected_label}' missing from Apple Wallet backFields!"

            print(f"    [OK] 100% Services Match for {count} Services!")

        print("\n" + "="*75)
        print("  ALL APPLE WALLET VS GOOGLE WALLET SERVICE TESTS PASSED 100%")
        print("="*75 + "\n")

    finally:
        db.close()

if __name__ == "__main__":
    test_apple_vs_google_services()
