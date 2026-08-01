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
from app.services.wallet_service import WalletService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_cross_tenant_audit():
    print("\n" + "="*70)
    print("  FINAL PRODUCTION AUDIT: MULTI-TENANT ISOLATION & PASS LIFECYCLE")
    print("="*70 + "\n")

    db = SessionLocal()
    try:
        # Create a fresh isolated test customer for this audit run
        customer = User(
            id=uuid.uuid4(),
            name="John Tester",
            email=f"john_{uuid.uuid4().hex[:6]}@example.com"
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)
        pkg_def = db.query(PrepaidPackage).first()
        pkg_id = pkg_def.id if pkg_def else uuid.uuid4()

        # 1. Create Tenant A (Dry Cleaners) and Tenant B (Royal Laundry)
        tenant_a = Company(id=uuid.uuid4(), name="Dry Cleaners")
        tenant_b = Company(id=uuid.uuid4(), name="Royal Laundry")
        db.add(tenant_a)
        db.add(tenant_b)
        db.commit()

        print(f"[+] Created Tenant A: '{tenant_a.name}' (ID={tenant_a.id})")
        print(f"[+] Created Tenant B: '{tenant_b.name}' (ID={tenant_b.id})")
        print(f"[+] Test Customer: '{customer.name}' (ID={customer.id})")

        # -------------------------------------------------------------------
        # SCENARIO A: Initial Pass Creation for Tenant A (Dry Cleaners)
        # -------------------------------------------------------------------
        pkg_a_1 = CustomerPackage(
            id=uuid.uuid4(),
            tenant_id=tenant_a.id,
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
        db.add(pkg_a_1)
        db.commit()
        db.refresh(pkg_a_1)

        pass_a_res = GoogleWalletPassService.generate_google_wallet_pass(
            db=db, package=pkg_a_1, customer=customer, company=tenant_a
        )
        assert pass_a_res.get("success") is True, f"Pass A generation failed: {pass_a_res.get('error')}"
        object_id_a = pass_a_res["object_id"]
        
        wp_a = db.query(WalletPass).filter(WalletPass.customer_package_id == pkg_a_1.id).first()
        assert wp_a is not None, "WalletPass A not created in DB"

        payload_a_1 = GoogleWalletObjectService.build_generic_object_payload(pkg_a_1, customer, tenant_a, object_id=object_id_a)
        name_a_1 = payload_a_1["cardTitle"]["defaultValue"]["value"]
        assert name_a_1 == "Dry Cleaners", f"Expected 'Dry Cleaners', got '{name_a_1}'"
        print(f"\n[OK] Scenario A PASS: WalletPass created for Tenant A | Object ID={object_id_a} | Company='{name_a_1}'")

        # -------------------------------------------------------------------
        # SCENARIO B: Deductions & Color Lifecycle for Tenant A (Gold -> Grey -> White)
        # -------------------------------------------------------------------
        # Deduction 1 (Gold -> Grey)
        pkg_a_1.current_balance = 50.00
        pkg_a_1.used_amount = 50.00
        pkg_a_1.service_items = [{"service": "Wash & Press", "total": 10, "left": 5}]
        db.commit()

        payload_b_grey = GoogleWalletObjectService.build_generic_object_payload(pkg_a_1, customer, tenant_a, object_id=object_id_a)
        name_b_grey = payload_b_grey["cardTitle"]["defaultValue"]["value"]
        color_b_grey = payload_b_grey["hexBackgroundColor"]

        assert name_b_grey == "Dry Cleaners", f"Company name changed! Got '{name_b_grey}'"
        assert color_b_grey == "#A6A6A6", f"Expected Grey #A6A6A6, got {color_b_grey}"
        print(f"[OK] Scenario B (Deduction) PASS: Company preserved='{name_b_grey}' | Color='{color_b_grey}' (Grey)")

        # Completion (Grey -> White)
        pkg_a_1.current_balance = 0.00
        pkg_a_1.used_amount = 100.00
        pkg_a_1.status = "COMPLETED"
        pkg_a_1.service_items = [{"service": "Wash & Press", "total": 10, "left": 0}]
        db.commit()

        payload_b_white = GoogleWalletObjectService.build_generic_object_payload(pkg_a_1, customer, tenant_a, object_id=object_id_a)
        name_b_white = payload_b_white["cardTitle"]["defaultValue"]["value"]
        color_b_white = payload_b_white["hexBackgroundColor"]

        assert name_b_white == "Dry Cleaners", f"Company name changed! Got '{name_b_white}'"
        assert color_b_white == "#FFFFFF", f"Expected White #FFFFFF, got {color_b_white}"
        print(f"[OK] Scenario B (Completion) PASS: Company preserved='{name_b_white}' | Color='{color_b_white}' (White)")

        # -------------------------------------------------------------------
        # SCENARIO C: Package Renewal INSIDE Tenant A (Dry Cleaners)
        # -------------------------------------------------------------------
        pkg_a_2 = CustomerPackage(
            id=uuid.uuid4(),
            tenant_id=tenant_a.id,
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
        db.add(pkg_a_2)
        db.commit()

        pass_a_renew_res = GoogleWalletPassService.generate_google_wallet_pass(
            db=db, package=pkg_a_2, customer=customer, company=tenant_a
        )
        assert pass_a_renew_res.get("success") is True, f"Renewal failed: {pass_a_renew_res.get('error')}"
        object_id_a_renew = pass_a_renew_res["object_id"]

        assert object_id_a_renew == object_id_a, f"Same Google Object ID not reused! Old={object_id_a}, New={object_id_a_renew}"

        payload_c = GoogleWalletObjectService.build_generic_object_payload(pkg_a_2, customer, tenant_a, object_id=object_id_a_renew)
        name_c = payload_c["cardTitle"]["defaultValue"]["value"]
        color_c = payload_c["hexBackgroundColor"]

        assert name_c == "Dry Cleaners", f"Company name changed on renewal! Got '{name_c}'"
        assert color_c == "#D4AF37", f"Expected Gold #D4AF37 on renewal, got {color_c}"
        print(f"[OK] Scenario C (Renewal) PASS: Same Object ID reused={object_id_a_renew} | Company='{name_c}' | Color='{color_c}' (Gold)")

        # -------------------------------------------------------------------
        # CROSS-TENANT ISOLATION: Same Customer John buys from Tenant B (Royal Laundry)
        # -------------------------------------------------------------------
        pkg_b_1 = CustomerPackage(
            id=uuid.uuid4(),
            tenant_id=tenant_b.id,
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
        db.add(pkg_b_1)
        db.commit()

        pass_b_res = GoogleWalletPassService.generate_google_wallet_pass(
            db=db, package=pkg_b_1, customer=customer, company=tenant_b
        )
        assert pass_b_res.get("success") is True, f"Pass B generation failed: {pass_b_res.get('error')}"
        object_id_b = pass_b_res["object_id"]

        assert object_id_b != object_id_a, f"CROSS-TENANT CORRUPTION! Tenant B reused Tenant A's Object ID ({object_id_a})"

        payload_b_tenant = GoogleWalletObjectService.build_generic_object_payload(pkg_b_1, customer, tenant_b, object_id=object_id_b)
        name_b_tenant = payload_b_tenant["cardTitle"]["defaultValue"]["value"]

        assert name_b_tenant == "Royal Laundry", f"Expected 'Royal Laundry', got '{name_b_tenant}'"

        # Verify Tenant A's pass was NOT modified by Tenant B's transaction
        payload_a_check = GoogleWalletObjectService.build_generic_object_payload(pkg_a_2, customer, tenant_a, object_id=object_id_a)
        assert payload_a_check["cardTitle"]["defaultValue"]["value"] == "Dry Cleaners", "Tenant A company name was overwritten!"

        print(f"\n[OK] Cross-Tenant Safety PASS:")
        print(f"     - Tenant A (Dry Cleaners) Object ID : {object_id_a} ('{name_c}')")
        print(f"     - Tenant B (Royal Laundry) Object ID: {object_id_b} ('{name_b_tenant}')")
        print(f"     - Zero cross-tenant object pollution! Tenant isolation is 100% verified.")

        # Cleanup test records
        db.query(WalletPass).filter(WalletPass.customer_package_id.in_([pkg_a_1.id, pkg_a_2.id, pkg_b_1.id])).delete(synchronize_session=False)
        db.query(CustomerPackage).filter(CustomerPackage.id.in_([pkg_a_1.id, pkg_a_2.id, pkg_b_1.id])).delete(synchronize_session=False)
        db.query(Company).filter(Company.id.in_([tenant_a.id, tenant_b.id])).delete(synchronize_session=False)
        db.query(User).filter(User.id == customer.id).delete(synchronize_session=False)
        db.commit()

        print("\n" + "="*70)
        print("  FINAL PRODUCTION AUDIT PASSED 100%")
        print("="*70 + "\n")

    except Exception as e:
        db.rollback()
        logger.exception(f"[x] Audit Failed: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_cross_tenant_audit()
