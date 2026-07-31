import os
import sys
import uuid
import datetime

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logging
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.company import Company
from app.models.user import User
from app.models.prepaid_package import PrepaidPackage
from app.models.customer_package import CustomerPackage
from app.models.wallet_pass import WalletPass
from app.services.google_wallet import (
    GoogleWalletAuthService,
    get_google_wallet_client,
    GoogleWalletClassService,
    GoogleWalletObjectService,
    GoogleWalletJwtService,
    GoogleWalletPassService
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_phase2_verification():
    summary = {
        "config": "FAIL",
        "authentication": "FAIL",
        "generic_class": "FAIL",
        "customer_package": "FAIL",
        "generic_object_id": "N/A",
        "generic_object": "FAIL",
        "object_fetch": "FAIL",
        "jwt_signing": "FAIL",
        "save_url": "FAIL",
        "db_storage": "FAIL",
        "final_result": "FAIL",
        "google_wallet_url": None
    }

    print("\n" + "="*60)
    print("      GOOGLE WALLET PHASE 2 VERIFICATION")
    print("="*60 + "\n")

    db = SessionLocal()

    try:
        # 1. Configuration
        if not settings.GOOGLE_WALLET_ENABLED or not settings.GOOGLE_WALLET_ISSUER_ID:
            print("[x] Configuration Error: Google Wallet disabled or missing Issuer ID")
            return print_summary(summary)
        summary["config"] = "PASS"
        print(f"[OK] Configuration Loaded: Issuer ID={settings.GOOGLE_WALLET_ISSUER_ID}")

        # 2. Authentication
        credentials = GoogleWalletAuthService.get_credentials()
        client = get_google_wallet_client()
        summary["authentication"] = "PASS"
        print(f"[OK] Authentication Successful: client_email={credentials.service_account_email}")

        # 3. Verify GenericClass
        class_res = GoogleWalletClassService.get_or_create_generic_class(client=client)
        summary["generic_class"] = class_res.get("status", "EXISTS")
        print(f"[OK] Generic Class Verified: Class ID={class_res['class_id']}")

        # 4. Load or Seed a real test CustomerPackage
        test_pkg = db.query(CustomerPackage).filter(CustomerPackage.status == "ACTIVE").order_by(CustomerPackage.purchase_date.desc()).first()
        
        if not test_pkg:
            print("[!] No active CustomerPackage found in DB. Seeding a clean test CustomerPackage...")
            comp = db.query(Company).first()
            if not comp:
                comp = Company(id=uuid.uuid4(), name="Laundra Qatar SaaS", code="LAUNDRAQATAR")
                db.add(comp)
                db.commit()
                
            cust = db.query(User).filter(User.role == "CUSTOMER").first()
            if not cust:
                cust = User(
                    id=uuid.uuid4(),
                    tenant_id=comp.id,
                    name="Phase 2 Test Customer",
                    email="phase2_test@laundra.qa",
                    phone="+97455001122",
                    password="hashedpassword",
                    role="CUSTOMER",
                    status="ACTIVE"
                )
                db.add(cust)
                db.commit()

            pkg_def = db.query(PrepaidPackage).first()
            if not pkg_def:
                pkg_def = PrepaidPackage(
                    id=uuid.uuid4(),
                    tenant_id=comp.id,
                    name="Silver VIP Package",
                    code="SILVERVIP",
                    original_price=100.0,
                    offer_price=80.0,
                    total_quantity=10,
                    is_active=True
                )
                db.add(pkg_def)
                db.commit()

            now_dt = datetime.datetime.utcnow()
            test_pkg = CustomerPackage(
                id=uuid.uuid4(),
                tenant_id=comp.id,
                customer_id=cust.id,
                package_id=pkg_def.id,
                purchase_date=now_dt,
                activation_date=now_dt,
                expiry_date=now_dt + datetime.timedelta(days=180),
                total_quantity=10,
                used_quantity=0,
                package_value=80.0,
                current_balance=80.0,
                used_amount=0.0,
                pass_color="GOLD",
                status="ACTIVE"
            )
            db.add(test_pkg)
            db.commit()
            db.refresh(test_pkg)

        summary["customer_package"] = f"FOUND (ID: {str(test_pkg.id)[:8]}...)"
        print(f"[OK] Customer Package Resolved: ID={test_pkg.id}")

        # 5. Deterministic Object ID & Object Creation
        object_id = GoogleWalletObjectService.get_object_id(test_pkg.id)
        summary["generic_object_id"] = object_id

        cust_obj = db.query(User).filter(User.id == test_pkg.customer_id).first()
        comp_obj = db.query(Company).filter(Company.id == test_pkg.tenant_id).first()

        object_res = GoogleWalletObjectService.get_or_create_generic_object(
            package=test_pkg,
            customer=cust_obj,
            company=comp_obj,
            client=client
        )
        summary["generic_object"] = object_res["status"]
        print(f"[OK] Generic Object Created/Verified: Object ID={object_id} (Status={object_res['status']})")

        # 6. Fetch Object back from Google API
        fetched_obj = GoogleWalletObjectService.get_generic_object(object_id=object_id, client=client)
        assert fetched_obj.get("id") == object_id, "Fetched object ID mismatch"
        summary["object_fetch"] = "PASS"
        print(f"[OK] Object Fetch Verification: State={fetched_obj.get('state')}")

        # 7. JWT Signing & Save URL Generation
        save_url = GoogleWalletJwtService.generate_save_url(object_payload=fetched_obj)
        summary["jwt_signing"] = "PASS"
        summary["save_url"] = "GENERATED"
        summary["google_wallet_url"] = "https://pay.google.com/gp/v/save/[REDACTED_JWT]"
        print("[OK] JWT Signing Successful. Save to Google Wallet URL Generated.")

        # 8. Database Storage Verification
        pass_res = GoogleWalletPassService.generate_google_wallet_pass(
            db=db,
            package=test_pkg,
            customer=cust_obj,
            company=comp_obj
        )

        assert pass_res["success"] is True, "Pass Service failed"
        
        # Verify persistence in DB
        db.refresh(test_pkg)
        wallet_pass = db.query(WalletPass).filter(WalletPass.customer_package_id == test_pkg.id).first()
        
        assert test_pkg.google_wallet_url is not None, "CustomerPackage.google_wallet_url is None"
        assert wallet_pass is not None and wallet_pass.google_wallet_url is not None, "WalletPass.google_wallet_url is None"
        
        summary["db_storage"] = "PASS"
        summary["final_result"] = "PASS"
        print(f"[OK] Database Storage Verified: WalletPass ID={wallet_pass.id}")

        print_summary(summary)

    except Exception as e:
        logger.exception(f"[x] Phase 2 Verification Error: {e}")
        print(f"[x] Verification Error: {e}")
        print_summary(summary)
    finally:
        db.close()

def print_summary(s: dict):
    print("\n" + "="*60)
    print("GOOGLE WALLET PHASE 2 VERIFICATION")
    print("="*60)
    print(f"Configuration        : {s['config']}")
    print(f"Authentication       : {s['authentication']}")
    print(f"Generic Class        : {s['generic_class']}")
    print(f"Customer Package     : {s['customer_package']}")
    print(f"Generic Object ID    : {s['generic_object_id']}")
    print(f"Generic Object       : {s['generic_object']}")
    print(f"Object Fetch         : {s['object_fetch']}")
    print(f"JWT Signing          : {s['jwt_signing']}")
    print(f"Save URL             : {s['save_url']}")
    print(f"Database Storage     : {s['db_storage']}")
    print(f"Final Result         : {s['final_result']}")
    print("="*60 + "\n")

    if s["google_wallet_url"]:
        print("[+] ADD TO GOOGLE WALLET URL (Copy & Open on Android Device):")
        print("-" * 60)
        print(s["google_wallet_url"])
        print("-" * 60 + "\n")

if __name__ == "__main__":
    run_phase2_verification()
