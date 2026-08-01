import os
import sys
import uuid
import datetime

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logging
from app.core.database import SessionLocal
from app.models.customer_package import CustomerPackage
from app.models.wallet_pass import WalletPass
from app.models.user import User
from app.models.company import Company
from app.services.google_wallet import (
    get_google_wallet_client,
    GoogleWalletAuthService,
    GoogleWalletClassService,
    GoogleWalletObjectService,
    GoogleWalletPassService
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_verification():
    print("\n" + "="*70)
    print("  VERIFYING GOOGLE WALLET: ALL SERVICES DISPLAYED & NO DUPLICATE TITLE")
    print("="*70 + "\n")

    db = SessionLocal()
    try:
        from app.models.prepaid_package import PrepaidPackage

        # Fetch or create test customer, company, and prepaid package
        customer = db.query(User).filter(User.name.isnot(None)).first()
        company = db.query(Company).first()
        pkg_def = db.query(PrepaidPackage).first()

        assert customer is not None, "Customer not found"
        assert company is not None, "Company not found"

        pkg_id = pkg_def.id if pkg_def else uuid.uuid4()

        # Create a test CustomerPackage with 3 services (Pressing, Wash & Press, Dry Cleaning)
        multi_service_package = CustomerPackage(
            id=uuid.uuid4(),
            tenant_id=company.id,
            customer_id=customer.id,
            package_id=pkg_id,
            purchase_date=datetime.datetime.utcnow(),
            total_quantity=17,
            package_value=84.00,
            current_balance=84.00,
            used_amount=0.0,
            status="ACTIVE",
            secure_token=str(uuid.uuid4()),
            pass_color="GOLD",
            service_items=[
                {"service": "Pressing", "total": 10, "left": 10},
                {"service": "Wash & Press", "total": 4, "left": 4},
                {"service": "Dry Cleaning", "total": 3, "left": 3}
            ]
        )
        db.add(multi_service_package)
        db.commit()
        db.refresh(multi_service_package)

        print(f"[+] Created Test Package ID: {multi_service_package.id}")
        print(f"    Services count: {len(multi_service_package.service_items)}")

        # 1. Test GenericClass patch & lookup
        class_res = GoogleWalletClassService.get_or_create_generic_class()
        class_id = class_res["class_id"]
        print(f"[OK] GenericClass verified: {class_id}")

        # 2. Test GenericObject payload construction
        payload = GoogleWalletObjectService.build_generic_object_payload(
            package=multi_service_package,
            customer=customer,
            company=company
        )

        # Verification 1: Header field is present to satisfy Google schema, set to company_name (not duplicate package_name)
        assert "header" in payload, "Header field is required by Google API schema"
        assert payload.get("header", {}).get("defaultValue", {}).get("value") == GoogleWalletObjectService.resolve_company_name(company)
        print(f"[OK] Header field satisfies Google schema with company name: '{payload.get('header', {}).get('defaultValue', {}).get('value')}'")

        # Verification 2: Card title bar has dynamic company name
        assert payload.get("cardTitle", {}).get("defaultValue", {}).get("value") == GoogleWalletObjectService.resolve_company_name(company)
        print(f"[OK] Dynamic SaaS company name present: '{payload.get('cardTitle', {}).get('defaultValue', {}).get('value')}'")

        # Verification 3: Inspect textModulesData
        text_modules = payload.get("textModulesData", [])
        module_headers = [tm["header"] for tm in text_modules]
        module_ids = [tm["id"] for tm in text_modules]

        print("\n--- Generated Text Modules ---")
        for tm in text_modules:
            print(f"  ID: {tm['id']:<15} | Header: {tm['header']:<25} | Body: {tm['body']}")

        # Ensure CUSTOMER, PACKAGE, COUPON COST, STATUS exist
        assert "customer" in module_ids, "CUSTOMER text module missing"
        assert "package" in module_ids, "PACKAGE text module missing"
        assert "coupon_cost" in module_ids, "COUPON COST text module missing"
        assert "status" in module_ids, "STATUS text module missing"

        # Ensure ALL 3 services are present: PRESSING LEFT, WASH & PRESS LEFT, DRY CLEANING LEFT
        assert "service_1" in module_ids, "service_1 missing"
        assert "service_2" in module_ids, "service_2 missing"
        assert "service_3" in module_ids, "service_3 (Dry Cleaning) missing!"

        assert "PRESSING LEFT" in module_headers, "PRESSING LEFT header missing"
        assert "WASH & PRESS LEFT" in module_headers, "WASH & PRESS LEFT header missing"
        assert "DRY CLEANING LEFT" in module_headers, "DRY CLEANING LEFT header missing!"

        print("\n[OK] All 3 package services successfully generated in payload:")
        print("  - service_1: PRESSING LEFT (10 / 10)")
        print("  - service_2: WASH & PRESS LEFT (4 / 4)")
        print("  - service_3: DRY CLEANING LEFT (3 / 3)")

        # 3. Test Live Google Wallet API call (Object Creation / Patching)
        pass_res = GoogleWalletPassService.generate_google_wallet_pass(
            db=db,
            package=multi_service_package,
            customer=customer,
            company=company
        )

        assert pass_res.get("success") is True, f"Pass generation failed: {pass_res.get('error')}"
        print(f"\n[OK] Live Google Wallet API call PASS!")
        print(f"     Save URL: https://pay.google.com/gp/v/save/[REDACTED_JWT]")

        # 4. Test package with 6 services (Ironing, Steam, Curtains, Carpet, Wash, Fold)
        six_service_package = CustomerPackage(
            id=uuid.uuid4(),
            tenant_id=company.id,
            customer_id=customer.id,
            package_id=pkg_id,
            purchase_date=datetime.datetime.utcnow(),
            total_quantity=58,
            package_value=250.00,
            current_balance=250.00,
            used_amount=0.0,
            status="ACTIVE",
            secure_token=str(uuid.uuid4()),
            pass_color="GOLD",
            service_items=[
                {"service": "Ironing", "total": 15, "left": 15},
                {"service": "Steam", "total": 5, "left": 5},
                {"service": "Curtains", "total": 2, "left": 2},
                {"service": "Carpet", "total": 1, "left": 1},
                {"service": "Wash", "total": 20, "left": 20},
                {"service": "Fold", "total": 20, "left": 20}
            ]
        )
        db.add(six_service_package)
        db.commit()
        db.refresh(six_service_package)

        payload_6 = GoogleWalletObjectService.build_generic_object_payload(
            package=six_service_package,
            customer=customer,
            company=company
        )
        tm_6_ids = [tm["id"] for tm in payload_6.get("textModulesData", [])]

        for s_idx in range(1, 7):
            assert f"service_{s_idx}" in tm_6_ids, f"service_{s_idx} missing in 6-service package!"
        print("\n[OK] 6-Service Package PASS: All 6 services rendered dynamically (service_1..service_6)")

        # Cleanup test records
        db.query(WalletPass).filter(WalletPass.customer_package_id.in_([multi_service_package.id, six_service_package.id])).delete(synchronize_session=False)
        db.query(CustomerPackage).filter(CustomerPackage.id.in_([multi_service_package.id, six_service_package.id])).delete(synchronize_session=False)
        db.commit()

        print("\n" + "="*70)
        print("  ALL VERIFICATION CHECKS PASSED 100%")
        print("="*70 + "\n")

    except Exception as e:
        db.rollback()
        logger.exception(f"[x] Verification failed: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_verification()
