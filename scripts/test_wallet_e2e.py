import sys
import os
import uuid
import datetime
import jwt
from decimal import Decimal
from sqlalchemy import text

# Add backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import SessionLocal, engine
from app.models.base import Base
from app.models.company import Company
from app.models.user import User
from app.models.prepaid_package import PrepaidPackage
from app.models.customer_package import CustomerPackage
from app.models.wallet_pass import WalletPass
from app.services.wallet_service import WalletService
from app.services.whatsapp_service import WhatsAppService
from app.wallet.class_service import create_or_get_generic_class

def run_production_e2e_tests():
    print("=======================================================")
    print("   GOOGLE WALLET END-TO-END PRODUCTION TEST SUITE")
    print("=======================================================\n")

    Base.metadata.create_all(bind=engine)
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE wallet_passes ADD COLUMN IF NOT EXISTS class_id VARCHAR(150);"))
            conn.execute(text("ALTER TABLE wallet_passes ADD COLUMN IF NOT EXISTS pass_status VARCHAR(20) DEFAULT 'ACTIVE';"))
            conn.execute(text("ALTER TABLE customer_packages ALTER COLUMN google_wallet_url TYPE TEXT;"))
            conn.execute(text("ALTER TABLE customer_packages ALTER COLUMN apple_wallet_url TYPE TEXT;"))
    except Exception as m_err:
        print(f"Migration notice: {m_err}")

    db = SessionLocal()

    try:
        # Step 1: Verify Generic Class
        print("[TEST 1/5] Verifying Google Wallet Generic Class...")
        class_res = create_or_get_generic_class()
        print(f"  -> Class Status: {class_res['status']} ({class_res.get('action', '')})")
        assert class_res["status"] == "SUCCESS", "Class verification failed"
        print("  -> TEST 1 PASSED [OK]\n")

        # Step 2: Setup Test Company, Customer, and Prepaid Package Definition
        print("[TEST 2/5] Setting up test Tenant, Customer, & Package...")
        test_company = db.query(Company).first()
        if not test_company:
            test_company = Company(id=uuid.uuid4(), name="E2E Laundry Qatar", code="E2EQATAR")
            db.add(test_company)
            db.commit()

        test_customer = db.query(User).filter(User.email == "e2e_wallet_customer@laundra.app").first()
        if not test_customer:
            test_customer = User(
                id=uuid.uuid4(),
                tenant_id=test_company.id,
                name="Ahmed Al-Mansoor",
                phone="+97455123456",
                email="e2e_wallet_customer@laundra.app",
                password="hashedpassword",
                role="CUSTOMER",
                status="ACTIVE"
            )
            db.add(test_customer)
            db.commit()

        test_pkg_def = db.query(PrepaidPackage).filter(PrepaidPackage.name == "Gold VIP Membership").first()
        if not test_pkg_def:
            test_pkg_def = PrepaidPackage(
                id=uuid.uuid4(),
                tenant_id=test_company.id,
                name="Gold VIP Membership",
                code="GOLDVIP",
                original_price=6000.0,
                offer_price=5000.0,
                total_quantity=20,
                eligible_services=["ALL"],
                validity_days=365,
                is_active=True
            )
            db.add(test_pkg_def)
            db.commit()

        print(f"  -> Customer: {test_customer.name} ({test_customer.phone})")
        print(f"  -> Package : {test_pkg_def.name} (QR {test_pkg_def.offer_price})")
        print("  -> TEST 2 PASSED [OK]\n")

        # Step 3: Phase 10 Package Purchase Integration
        print("[TEST 3/5] Simulating Package Purchase & Wallet Pass Persistence...")
        activation_date = datetime.datetime.utcnow()
        expiry_date = activation_date + datetime.timedelta(days=365)

        cust_pkg = CustomerPackage(
            id=uuid.uuid4(),
            tenant_id=test_company.id,
            customer_id=test_customer.id,
            package_id=test_pkg_def.id,
            purchase_date=activation_date,
            activation_date=activation_date,
            expiry_date=expiry_date,
            total_quantity=20,
            used_quantity=0,
            package_value=5000.0,
            current_balance=5000.0,
            used_amount=0.0,
            pass_color="GOLD",
            status="ACTIVE"
        )
        db.add(cust_pkg)
        db.commit()
        db.refresh(cust_pkg)

        # Save Wallet Pass using Orchestrator
        wallet_pass = WalletService.create_and_save_wallet_pass(
            db=db,
            package=cust_pkg,
            customer=test_customer,
            company_name=test_company.name
        )

        assert wallet_pass is not None, "WalletPass record creation failed"
        assert cust_pkg.google_wallet_url is not None, "Google Wallet URL failed"
        assert "pay.google.com/gp/v/save" in cust_pkg.google_wallet_url, "Invalid Google Wallet Save URL"

        print(f"  -> WalletPass DB ID : {wallet_pass.id}")
        print(f"  -> Object ID        : {wallet_pass.object_id}")
        print(f"  -> Wallet Pass Link : {cust_pkg.google_wallet_url[:65]}...")

        # Phase 12 WhatsApp Integration Test
        WhatsAppService.send_package_activated_message(test_customer, cust_pkg)
        print("  -> TEST 3 PASSED [OK]\n")

        # Step 4: Phase 11 Automatic Wallet Updates (Redemption)
        print("[TEST 4/5] Simulating POS Redemption & Automatic Pass Update...")
        cust_pkg.used_quantity += 3
        cust_pkg.current_balance -= Decimal('750.0')
        cust_pkg.used_amount += Decimal('750.0')

        # Call orchestrator update
        WalletService.update_wallet_pass_on_usage(db=db, package=cust_pkg, customer=test_customer)

        updated_pass = db.query(WalletPass).filter(WalletPass.customer_package_id == cust_pkg.id).first()
        assert updated_pass is not None, "Updated WalletPass record not found"
        print(f"  -> Updated Items Remaining : {cust_pkg.total_quantity - cust_pkg.used_quantity} items")
        print(f"  -> Updated Balance         : QR {cust_pkg.current_balance:.2f}")
        print("  -> TEST 4 PASSED [OK]\n")

        # Step 5: Package Fully Utilized / Status Update Test
        print("[TEST 5/5] Simulating Full Package Utilization & Expiry Status...")
        cust_pkg.used_quantity = cust_pkg.total_quantity
        cust_pkg.current_balance = Decimal('0.0')
        cust_pkg.status = "FULLY_UTILIZED"

        WalletService.update_wallet_pass_on_usage(db=db, package=cust_pkg, customer=test_customer)

        final_pass = db.query(WalletPass).filter(WalletPass.customer_package_id == cust_pkg.id).first()
        assert final_pass.pass_status == "FULLY_UTILIZED", "Pass status update failed"
        print(f"  -> Final Pass Status : {final_pass.pass_status}")
        print("  -> TEST 5 PASSED [OK]\n")

        print("=======================================================")
        print("   ALL 5 END-TO-END PRODUCTION TESTS PASSED (100%)")
        print("=======================================================")

    except Exception as e:
        print(f"\n[ERROR] E2E TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    run_production_e2e_tests()
