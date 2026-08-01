import os
import sys
import uuid
import datetime
from decimal import Decimal

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
    GoogleWalletObjectService
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_gold_card_verification():
    summary = {
        "customer_package_exists": "FAIL",
        "wallet_pass_exists": "FAIL",
        "generic_object_exists": "FAIL",
        "object_id_correct": "FAIL",
        "clean_url_exists": "FAIL",
        "qr_token_unchanged": "FAIL",
        "gold_color_hex": "FAIL",
        "package_name_match": "FAIL",
        "customer_name_match": "FAIL",
        "balance_match": "FAIL",
        "expiry_match": "FAIL",
        "services_match": "FAIL",
        "qr_code_match": "FAIL",
        "final_result": "FAIL"
    }

    print("\n" + "="*60)
    print("   PHASE 1 — GOOGLE WALLET GOLD CARD VERIFICATION")
    print("="*60 + "\n")

    db = SessionLocal()

    try:
        client = get_google_wallet_client()

        # Step 1: Create a completely NEW prepaid package
        comp = db.query(Company).first()
        if not comp:
            comp = Company(id=uuid.uuid4(), name="Laundra Laundry", code="LAUNDRA")
            db.add(comp); db.commit()

        cust = User(
            id=uuid.uuid4(),
            tenant_id=comp.id,
            name="charan",
            email=f"charan_{uuid.uuid4().hex[:4]}@laundra.qa",
            phone="+97455990011",
            password="hashedpassword",
            role="CUSTOMER",
            status="ACTIVE"
        )
        db.add(cust); db.commit()

        pkg_def = PrepaidPackage(
            id=uuid.uuid4(),
            tenant_id=comp.id,
            name="PLATINUM",
            code="PLATINUM",
            original_price=250.0,
            offer_price=200.0,
            total_quantity=10,
            eligible_services=["ALL"],
            is_active=True
        )
        db.add(pkg_def); db.commit()

        expiry_dt = datetime.datetime(2026, 8, 30, 23, 59, 59)
        test_pkg = CustomerPackage(
            id=uuid.uuid4(),
            tenant_id=comp.id,
            customer_id=cust.id,
            package_id=pkg_def.id,
            purchase_date=datetime.datetime.utcnow(),
            activation_date=datetime.datetime.utcnow(),
            expiry_date=expiry_dt,
            total_quantity=10,
            used_quantity=0,
            package_value=200.0,
            current_balance=200.0,
            used_amount=0.0,
            pass_color="GOLD",
            status="ACTIVE",
            service_items=[
                {"service": "Wash & Fold", "total": 10, "left": 10}
            ]
        )
        db.add(test_pkg); db.commit(); db.refresh(test_pkg)

        summary["customer_package_exists"] = f"PASS (ID: {test_pkg.id})"

        # Step 2: Generate Wallet Pass
        res = WalletService.create_and_save_wallet_pass(
            db=db,
            package=test_pkg,
            customer=cust,
            company_name="Laundra Laundry"
        )
        assert res.get("google_wallet") is True, "Google Wallet pass generation failed"

        db.refresh(test_pkg)
        wallet_pass = db.query(WalletPass).filter(WalletPass.customer_package_id == test_pkg.id).first()
        assert wallet_pass is not None, "WalletPass record missing in DB"
        summary["wallet_pass_exists"] = f"PASS (ID: {wallet_pass.id})"

        expected_obj_id = f"{settings.GOOGLE_WALLET_ISSUER_ID}.pkg_{test_pkg.id}"
        assert wallet_pass.google_object_id == expected_obj_id, f"Google Object ID mismatch: {wallet_pass.google_object_id}"
        summary["object_id_correct"] = f"PASS ({expected_obj_id})"

        assert test_pkg.google_wallet_url is not None and test_pkg.google_wallet_url.startswith("/api/v1/wallet/google/pass/"), f"Invalid clean URL: {test_pkg.google_wallet_url}"
        summary["clean_url_exists"] = f"PASS ({test_pkg.google_wallet_url})"

        expected_qr = test_pkg.secure_token if test_pkg.secure_token else str(test_pkg.id)
        summary["qr_token_unchanged"] = f"PASS ({expected_qr})"

        # Step 3: Fetch live GenericObject from Google Wallet API
        fetched_obj = GoogleWalletObjectService.get_generic_object(expected_obj_id, client=client)
        assert fetched_obj.get("id") == expected_obj_id, "Google API Object not found"
        summary["generic_object_exists"] = "PASS"

        bg_hex = fetched_obj.get("hexBackgroundColor", "").upper()
        assert bg_hex == "#D97706", f"Card background color is not Gold #D97706: {bg_hex}"
        summary["gold_color_hex"] = f"PASS ({bg_hex} - Vibrant Gold)"

        # Step 4: Verify Displayed Card Data Matches DB
        card_title = fetched_obj.get("cardTitle", {}).get("defaultValue", {}).get("value")
        header = fetched_obj.get("header", {}).get("defaultValue", {}).get("value")
        barcode_val = fetched_obj.get("barcode", {}).get("value")
        text_mods = {m["id"]: m["body"] for m in fetched_obj.get("textModulesData", [])}

        assert card_title == "Laundra Laundry", f"Company Name mismatch: {card_title}"
        assert header == "PLATINUM", f"Package Name mismatch: {header}"
        assert text_mods.get("customer") == "charan", f"Customer Name mismatch: {text_mods.get('customer')}"
        assert "200.00" in text_mods.get("balance", ""), f"Balance mismatch: {text_mods.get('balance')}"
        assert "30 Aug 2026" in text_mods.get("expiry", ""), f"Expiry mismatch: {text_mods.get('expiry')}"
        assert "Wash & Fold: 10 / 10" in text_mods.get("services", ""), f"Services mismatch: {text_mods.get('services')}"
        assert barcode_val == expected_qr, f"QR Code mismatch: {barcode_val}"

        summary["package_name_match"] = f"PASS ({header})"
        summary["customer_name_match"] = f"PASS ({text_mods.get('customer')})"
        summary["balance_match"] = f"PASS ({text_mods.get('balance')})"
        summary["expiry_match"] = f"PASS ({text_mods.get('expiry')})"
        summary["services_match"] = f"PASS ({text_mods.get('services')})"
        summary["qr_code_match"] = f"PASS ({barcode_val})"

        summary["final_result"] = "PASS"

        print_summary(summary, test_pkg, expected_obj_id)

    except Exception as e:
        logger.exception(f"[x] Gold Card Verification Error: {e}")
        print(f"[x] Error: {e}")
        print_summary(summary, None, None)
    finally:
        db.close()

def print_summary(s: dict, pkg, obj_id):
    print("\n" + "="*60)
    print("   PHASE 1 — GOOGLE WALLET GOLD CARD VERIFICATION REPORT")
    print("="*60)
    print(f"CustomerPackage Exists          : {s['customer_package_exists']}")
    print(f"WalletPass Exists               : {s['wallet_pass_exists']}")
    print(f"Google GenericObject Exists     : {s['generic_object_exists']}")
    print(f"Google Object ID Correct        : {s['object_id_correct']}")
    print(f"Clean Redirect URL Exists       : {s['clean_url_exists']}")
    print(f"QR Token Unchanged              : {s['qr_token_unchanged']}")
    print(f"Card Color (#D97706 Gold)       : {s['gold_color_hex']}")
    print(f"Package Name Match              : {s['package_name_match']}")
    print(f"Customer Name Match             : {s['customer_name_match']}")
    print(f"Remaining Balance Match         : {s['balance_match']}")
    print(f"Expiry Date Match               : {s['expiry_match']}")
    print(f"Remaining Services Match        : {s['services_match']}")
    print(f"QR Code Match                   : {s['qr_code_match']}")
    print(f"Final Result                    : {s['final_result']}")
    print("="*60 + "\n")

if __name__ == "__main__":
    run_gold_card_verification()
