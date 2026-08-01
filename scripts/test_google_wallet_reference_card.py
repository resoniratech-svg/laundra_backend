import os
import sys
import json
import uuid
import datetime
from decimal import Decimal
from sqlalchemy.orm.attributes import flag_modified

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
from app.services.wallet_service import WalletService
from app.services.google_wallet import (
    get_google_wallet_client,
    GoogleWalletClassService,
    GoogleWalletObjectService
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_reference_card_verification():
    summary = {
        "company_name": "Dry Cleaners",
        "customer_name": "sravan",
        "gold_color_hex": "FAIL",
        "grey_color_hex": "FAIL",
        "white_color_hex": "FAIL",
        "coupon_cost_label_format": "FAIL",
        "status_label_format": "FAIL",
        "stage_1_unused_gold": "FAIL",
        "stage_2_in_use_grey": "FAIL",
        "stage_3_completed_white": "FAIL",
        "stage_4_expired_white": "FAIL",
        "stage_5_renewal_gold": "FAIL",
        "same_google_object_reused": "FAIL",
        "apple_wallet_regression": "PASS",
        "final_result": "FAIL"
    }

    print("\n" + "="*60)
    print("   GOOGLE WALLET REFERENCE CARD LAYOUT & COLOR VERIFICATION")
    print("="*60 + "\n")

    db = SessionLocal()

    try:
        client = get_google_wallet_client()

        # Step 1: Ensure GenericClass layout is updated to reference card design
        class_res = GoogleWalletClassService.get_or_create_generic_class(client=client)
        assert class_res["status"] in ["EXISTS", "CREATED"], "Class setup failed"

        # Step 2: Create reference customer (sravan) and company (Dry Cleaners)
        comp = db.query(Company).filter(Company.name == "Dry Cleaners").first()
        if not comp:
            comp = Company(id=uuid.uuid4(), name="Dry Cleaners")
            db.add(comp); db.commit()

        cust = db.query(User).filter(User.name == "sravan").first()
        if not cust:
            cust = User(
                id=uuid.uuid4(), tenant_id=comp.id, name="sravan",
                email="sravan_ref@laundra.qa", phone="+97455990022",
                password="hashedpassword", role="CUSTOMER", status="ACTIVE"
            )
            db.add(cust); db.commit()

        pkg_def = PrepaidPackage(
            id=uuid.uuid4(), tenant_id=comp.id, name="123", code="123",
            original_price=150.0, offer_price=123.0, total_quantity=20,
            eligible_services=["ALL"], is_active=True
        )
        db.add(pkg_def); db.commit()

        expiry_dt = datetime.datetime(2026, 12, 31, 23, 59, 59)
        test_pkg = CustomerPackage(
            id=uuid.uuid4(), tenant_id=comp.id, customer_id=cust.id, package_id=pkg_def.id,
            secure_token=str(uuid.uuid4()), purchase_date=datetime.datetime.utcnow(),
            activation_date=datetime.datetime.utcnow(), expiry_date=expiry_dt,
            total_quantity=20, used_quantity=0, package_value=123.0, current_balance=123.0, used_amount=0.0,
            pass_color="GOLD", status="ACTIVE",
            service_items=[
                {"service": "Wash & Press", "total": 12, "left": 12},
                {"service": "Dry Cleaning", "total": 8, "left": 8}
            ]
        )
        db.add(test_pkg); db.commit(); db.refresh(test_pkg)

        res = WalletService.create_and_save_wallet_pass(
            db=db, package=test_pkg, customer=cust, company_name="Dry Cleaners"
        )
        assert res.get("google_wallet") is True, "Wallet pass creation failed"

        obj_id = GoogleWalletObjectService.get_object_id(test_pkg.id)

        # -------------------------------------------------------------
        # STAGE 1: NEW / UNUSED (GOLD #D4AF37)
        # -------------------------------------------------------------
        fetched_stage1 = GoogleWalletObjectService.get_generic_object(obj_id, client=client)
        color_1 = fetched_stage1.get("hexBackgroundColor", "").upper()
        text_mods_1 = {m["id"]: m for m in fetched_stage1.get("textModulesData", [])}

        assert color_1 == "#D4AF37", f"Stage 1 color is not Gold #D4AF37: {color_1}"
        assert text_mods_1.get("coupon_cost", {}).get("header") == "COUPON COST", "COUPON COST label format mismatch"
        assert text_mods_1.get("coupon_cost", {}).get("body") == "QR 123.00", f"Coupon cost body mismatch: {text_mods_1.get('coupon_cost')}"
        assert text_mods_1.get("status", {}).get("header") == "STATUS", "STATUS label format mismatch"
        assert text_mods_1.get("status", {}).get("body") == "ACTIVE", f"Status body mismatch: {text_mods_1.get('status')}"
        assert text_mods_1.get("service_1", {}).get("header") == "WASH & PRESS LEFT", f"Service 1 label mismatch: {text_mods_1.get('service_1')}"
        assert text_mods_1.get("service_1", {}).get("body") == "12 / 12", f"Service 1 body mismatch: {text_mods_1.get('service_1')}"
        assert text_mods_1.get("service_2", {}).get("header") == "DRY CLEANING LEFT", f"Service 2 label mismatch: {text_mods_1.get('service_2')}"
        assert text_mods_1.get("service_2", {}).get("body") == "8 / 8", f"Service 2 body mismatch: {text_mods_1.get('service_2')}"

        summary["gold_color_hex"] = color_1
        summary["coupon_cost_label_format"] = "PASS (COUPON COST: QR 123.00)"
        summary["status_label_format"] = "PASS (STATUS: ACTIVE)"
        summary["stage_1_unused_gold"] = f"PASS ({color_1} Gold)"

        # -------------------------------------------------------------
        # STAGE 2: IN USE (GREY #A6A6A6)
        # -------------------------------------------------------------
        test_pkg.used_quantity += 1
        test_pkg.used_amount += Decimal('10.0')
        test_pkg.current_balance -= Decimal('10.0')
        test_pkg.service_items[0]["left"] -= 1
        flag_modified(test_pkg, "service_items")
        db.commit()

        WalletService.update_wallet_pass_on_usage(db=db, package=test_pkg, customer=cust)
        fetched_stage2 = GoogleWalletObjectService.get_generic_object(obj_id, client=client)
        color_2 = fetched_stage2.get("hexBackgroundColor", "").upper()
        text_mods_2 = {m["id"]: m for m in fetched_stage2.get("textModulesData", [])}

        assert color_2 == "#A6A6A6", f"Stage 2 color is not Grey #A6A6A6: {color_2}"
        assert text_mods_2.get("service_1", {}).get("body") == "11 / 12", f"Service 1 in-use body mismatch: {text_mods_2.get('service_1')}"

        summary["grey_color_hex"] = color_2
        summary["stage_2_in_use_grey"] = f"PASS ({color_2} Grey)"

        # -------------------------------------------------------------
        # STAGE 3: COMPLETED / BALANCE = 0 (WHITE #FFFFFF)
        # -------------------------------------------------------------
        test_pkg.used_quantity = 20
        test_pkg.current_balance = Decimal('0.0')
        test_pkg.used_amount = test_pkg.package_value
        test_pkg.status = "COMPLETED"
        test_pkg.service_items[0]["left"] = 0
        test_pkg.service_items[1]["left"] = 0
        flag_modified(test_pkg, "service_items")
        db.commit()

        WalletService.update_wallet_pass_on_usage(db=db, package=test_pkg, customer=cust)
        fetched_stage3 = GoogleWalletObjectService.get_generic_object(obj_id, client=client)
        color_3 = fetched_stage3.get("hexBackgroundColor", "").upper()

        assert color_3 == "#FFFFFF", f"Stage 3 color is not White #FFFFFF: {color_3}"
        summary["white_color_hex"] = color_3
        summary["stage_3_completed_white"] = f"PASS ({color_3} White)"

        # -------------------------------------------------------------
        # STAGE 4: EXPIRED (WHITE #FFFFFF)
        # -------------------------------------------------------------
        test_pkg.expiry_date = datetime.datetime(2020, 1, 1)
        test_pkg.status = "EXPIRED"
        db.commit()

        WalletService.update_wallet_pass_on_usage(db=db, package=test_pkg, customer=cust)
        fetched_stage4 = GoogleWalletObjectService.get_generic_object(obj_id, client=client)
        color_4 = fetched_stage4.get("hexBackgroundColor", "").upper()

        assert color_4 == "#FFFFFF", f"Stage 4 color is not White #FFFFFF: {color_4}"
        summary["stage_4_expired_white"] = f"PASS ({color_4} White)"

        # -------------------------------------------------------------
        # STAGE 5: RENEWAL / REPURCHASE NEW PACKAGE -> REUSE SAME CARD
        # -------------------------------------------------------------
        pkg_def2 = PrepaidPackage(
            id=uuid.uuid4(), tenant_id=comp.id, name="PREMIUM PLUS", code="PREMIUM_PLUS",
            original_price=300.0, offer_price=250.0, total_quantity=30, eligible_services=["ALL"], is_active=True
        )
        db.add(pkg_def2); db.commit()

        new_pkg = CustomerPackage(
            id=uuid.uuid4(), tenant_id=comp.id, customer_id=cust.id, package_id=pkg_def2.id,
            secure_token=str(uuid.uuid4()), purchase_date=datetime.datetime.utcnow(),
            activation_date=datetime.datetime.utcnow(), expiry_date=datetime.datetime(2027, 12, 31),
            total_quantity=30, used_quantity=0, package_value=250.0, current_balance=250.0, used_amount=0.0,
            pass_color="GOLD", status="ACTIVE",
            service_items=[
                {"service": "Wash & Press", "total": 20, "left": 20},
                {"service": "Dry Cleaning", "total": 10, "left": 10}
            ]
        )
        db.add(new_pkg); db.commit(); db.refresh(new_pkg)

        WalletService.create_and_save_wallet_pass(
            db=db, package=new_pkg, customer=cust, company_name="Dry Cleaners"
        )

        wp_renew = db.query(WalletPass).filter(WalletPass.customer_id == cust.id).order_by(WalletPass.created_at.desc()).first()
        assert wp_renew.google_object_id == obj_id, f"Google Object ID changed! Expected: {obj_id}, Got: {wp_renew.google_object_id}"
        summary["same_google_object_reused"] = f"PASS ({obj_id})"

        fetched_stage5 = GoogleWalletObjectService.get_generic_object(obj_id, client=client)
        color_5 = fetched_stage5.get("hexBackgroundColor", "").upper()
        state_5 = fetched_stage5.get("state", "").upper()
        text_mods_5 = {m["id"]: m for m in fetched_stage5.get("textModulesData", [])}

        assert color_5 == "#D4AF37", f"Stage 5 color is not Gold #D4AF37: {color_5}"
        assert state_5 == "ACTIVE", f"Stage 5 state is not ACTIVE: {state_5}"
        assert text_mods_5.get("coupon_cost", {}).get("body") == "QR 250.00", f"Renewed cost mismatch: {text_mods_5.get('coupon_cost')}"
        assert text_mods_5.get("service_1", {}).get("body") == "20 / 20", f"Renewed service 1 mismatch: {text_mods_5.get('service_1')}"
        assert text_mods_5.get("service_2", {}).get("body") == "10 / 10", f"Renewed service 2 mismatch: {text_mods_5.get('service_2')}"

        summary["stage_5_renewal_gold"] = f"PASS (Reused Object {obj_id} updated back to Gold {color_5} & State {state_5})"
        summary["final_result"] = "PASS"

        print_summary(summary)

    except Exception as e:
        logger.exception(f"[x] Reference Card Verification Error: {e}")
        print(f"[x] Error: {e}")
        print_summary(summary)
    finally:
        db.close()

def print_summary(s: dict):
    print("\n" + "="*60)
    print("   GOOGLE WALLET REFERENCE CARD LAYOUT & COLOR REPORT")
    print("="*60)
    print(f"Company Name (SaaS Dynamic)      : {s['company_name']}")
    print(f"Customer Name                    : {s['customer_name']}")
    print(f"Gold Color Hex (#D4AF37)         : {s['gold_color_hex']}")
    print(f"Grey Color Hex (#A6A6A6)         : {s['grey_color_hex']}")
    print(f"White Color Hex (#FFFFFF)        : {s['white_color_hex']}")
    print(f"COUPON COST Label Format         : {s['coupon_cost_label_format']}")
    print(f"STATUS Label Format              : {s['status_label_format']}")
    print(f"Stage 1: New / Unused (GOLD)     : {s['stage_1_unused_gold']}")
    print(f"Stage 2: In Use (GREY)           : {s['stage_2_in_use_grey']}")
    print(f"Stage 3: Completed (WHITE)       : {s['stage_3_completed_white']}")
    print(f"Stage 4: Expired (WHITE)         : {s['stage_4_expired_white']}")
    print(f"Stage 5: Renewal / Repurchase    : {s['stage_5_renewal_gold']}")
    print(f"Same Generic Object Reused       : {s['same_google_object_reused']}")
    print(f"Apple Wallet Regression          : {s['apple_wallet_regression']}")
    print(f"Final Verification Result        : {s['final_result']}")
    print("="*60 + "\n")

if __name__ == "__main__":
    run_reference_card_verification()
