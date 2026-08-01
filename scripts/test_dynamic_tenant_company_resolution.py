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
from app.models.prepaid_package import PrepaidPackage
from app.services.google_wallet import (
    GoogleWalletObjectService,
    GoogleWalletPassService,
    GoogleWalletClassService
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_dynamic_tenant_company():
    print("\n" + "="*70)
    print("  VERIFYING DYNAMIC SAAS TENANT COMPANY NAME & PATCH PINNING")
    print("="*70 + "\n")

    db = SessionLocal()
    try:
        customer = db.query(User).filter(User.name.isnot(None)).first()
        pkg_def = db.query(PrepaidPackage).first()
        assert customer is not None, "Customer not found"
        pkg_id = pkg_def.id if pkg_def else uuid.uuid4()

        # 1. Create two separate SaaS tenant companies
        company_qatar = Company(
            id=uuid.uuid4(),
            name="Laundry Qatar"
        )
        company_royal = Company(
            id=uuid.uuid4(),
            name="Royal Laundry"
        )
        db.add(company_qatar)
        db.add(company_royal)
        db.commit()

        print(f"[+] Created Tenant 1: '{company_qatar.name}' (ID={company_qatar.id})")
        print(f"[+] Created Tenant 2: '{company_royal.name}' (ID={company_royal.id})")

        # 2. Create CustomerPackage for Tenant 1 (Laundry Qatar)
        pkg_qatar = CustomerPackage(
            id=uuid.uuid4(),
            tenant_id=company_qatar.id,
            customer_id=customer.id,
            package_id=pkg_id,
            purchase_date=datetime.datetime.utcnow(),
            total_quantity=10,
            package_value=100.00,
            current_balance=100.00,
            used_amount=0.0,
            status="ACTIVE",
            secure_token=str(uuid.uuid4()),
            pass_color="GOLD",
            service_items=[{"service": "Wash & Press", "total": 10, "left": 10}]
        )
        db.add(pkg_qatar)
        db.commit()
        db.refresh(pkg_qatar)

        # Test initial pass creation payload resolution
        payload_qatar = GoogleWalletObjectService.build_generic_object_payload(
            package=pkg_qatar,
            customer=customer,
            company=company_qatar
        )
        card_title_qatar = payload_qatar["cardTitle"]["defaultValue"]["value"]
        header_qatar = payload_qatar["header"]["defaultValue"]["value"]

        assert card_title_qatar == "Laundry Qatar", f"Expected 'Laundry Qatar', got '{card_title_qatar}'"
        assert header_qatar == "Laundry Qatar", f"Expected 'Laundry Qatar', got '{header_qatar}'"
        print(f"\n[OK] Initial Pass Creation Tenant 1 PASS: CardTitle='{card_title_qatar}' | Header='{header_qatar}'")

        # 3. Simulate usage deduction & color transition Gold -> Grey for Tenant 1 without passing company object
        pkg_qatar.current_balance = 80.00
        pkg_qatar.used_amount = 20.00
        pkg_qatar.service_items = [{"service": "Wash & Press", "total": 10, "left": 8}]
        db.commit()

        # Call build_generic_object_payload WITHOUT company object
        payload_deduct = GoogleWalletObjectService.build_generic_object_payload(
            package=pkg_qatar,
            customer=customer,
            company=None
        )
        card_title_deduct = payload_deduct["cardTitle"]["defaultValue"]["value"]
        color_deduct = payload_deduct["hexBackgroundColor"]

        assert card_title_deduct == "Laundry Qatar", f"Company name changed during deduction! Got '{card_title_deduct}'"
        assert color_deduct == "#A6A6A6", f"Expected Grey #A6A6A6, got {color_deduct}"
        print(f"[OK] Deduction Patch Tenant 1 PASS: Company preserved='{card_title_deduct}' | Color='{color_deduct}' (Grey)")

        # 4. Simulate Completion -> White (#FFFFFF)
        pkg_qatar.current_balance = 0.00
        pkg_qatar.used_amount = 100.00
        pkg_qatar.status = "COMPLETED"
        pkg_qatar.service_items = [{"service": "Wash & Press", "total": 10, "left": 0}]
        db.commit()

        payload_completed = GoogleWalletObjectService.build_generic_object_payload(
            package=pkg_qatar,
            customer=customer,
            company=None
        )
        card_title_completed = payload_completed["cardTitle"]["defaultValue"]["value"]
        color_completed = payload_completed["hexBackgroundColor"]

        assert card_title_completed == "Laundry Qatar", f"Company name changed during completion! Got '{card_title_completed}'"
        assert color_completed == "#FFFFFF", f"Expected White #FFFFFF, got {color_completed}"
        print(f"[OK] Completion Patch Tenant 1 PASS: Company preserved='{card_title_completed}' | Color='{color_completed}' (White)")

        # 5. Simulate Renewal within Tenant 1 -> Gold (#D4AF37)
        pkg_qatar_renewed = CustomerPackage(
            id=uuid.uuid4(),
            tenant_id=company_qatar.id,
            customer_id=customer.id,
            package_id=pkg_id,
            purchase_date=datetime.datetime.utcnow(),
            total_quantity=20,
            package_value=200.00,
            current_balance=200.00,
            used_amount=0.0,
            status="ACTIVE",
            secure_token=str(uuid.uuid4()),
            pass_color="GOLD",
            service_items=[{"service": "Wash & Press", "total": 20, "left": 20}]
        )
        db.add(pkg_qatar_renewed)
        db.commit()

        payload_renewal = GoogleWalletObjectService.build_generic_object_payload(
            package=pkg_qatar_renewed,
            customer=customer,
            company=None
        )
        card_title_renewal = payload_renewal["cardTitle"]["defaultValue"]["value"]
        color_renewal = payload_renewal["hexBackgroundColor"]

        assert card_title_renewal == "Laundry Qatar", f"Company name changed during renewal! Got '{card_title_renewal}'"
        assert color_renewal == "#D4AF37", f"Expected Gold #D4AF37, got {color_renewal}"
        print(f"[OK] Renewal Patch Tenant 1 PASS: Company preserved='{card_title_renewal}' | Color='{color_renewal}' (Gold)")

        # 6. Test Tenant 2 (Royal Laundry) - Independent Pass
        pkg_royal = CustomerPackage(
            id=uuid.uuid4(),
            tenant_id=company_royal.id,
            customer_id=customer.id,
            package_id=pkg_id,
            purchase_date=datetime.datetime.utcnow(),
            total_quantity=15,
            package_value=150.00,
            current_balance=150.00,
            used_amount=0.0,
            status="ACTIVE",
            secure_token=str(uuid.uuid4()),
            pass_color="GOLD",
            service_items=[{"service": "Dry Cleaning", "total": 15, "left": 15}]
        )
        db.add(pkg_royal)
        db.commit()

        payload_royal = GoogleWalletObjectService.build_generic_object_payload(
            package=pkg_royal,
            customer=customer,
            company=None
        )
        card_title_royal = payload_royal["cardTitle"]["defaultValue"]["value"]

        assert card_title_royal == "Royal Laundry", f"Expected 'Royal Laundry', got '{card_title_royal}'"
        print(f"[OK] Initial Pass Creation Tenant 2 PASS: CardTitle='{card_title_royal}'")

        # Cleanup test records
        db.query(CustomerPackage).filter(CustomerPackage.id.in_([pkg_qatar.id, pkg_qatar_renewed.id, pkg_royal.id])).delete(synchronize_session=False)
        db.query(Company).filter(Company.id.in_([company_qatar.id, company_royal.id])).delete(synchronize_session=False)
        db.commit()

        print("\n" + "="*70)
        print("  ALL DYNAMIC SAAS TENANT VERIFICATION CHECKS PASSED 100%")
        print("="*70 + "\n")

    except Exception as e:
        db.rollback()
        logger.exception(f"[x] Dynamic Tenant Test Failed: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    test_dynamic_tenant_company()
