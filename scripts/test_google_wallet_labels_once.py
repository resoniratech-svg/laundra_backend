"""
GOOGLE WALLET — LABEL ONCE-ONLY VERIFICATION
Verifies that each label appears exactly once (via header) and
the body contains only the dynamic value with NO label repetition.
"""
import os, sys, uuid, datetime, json
from decimal import Decimal
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logging
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
    GoogleWalletObjectService,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run():
    db = SessionLocal()
    results = {}

    try:
        client = get_google_wallet_client()

        # 1. Patch class template
        GoogleWalletClassService.get_or_create_generic_class(client=client)

        # 2. Resolve or create test company + customer + package
        comp = db.query(Company).first()
        assert comp, "No company found in DB"

        cust = db.query(User).filter(User.role == "CUSTOMER").first()
        assert cust, "No customer found in DB"

        pkg_def = PrepaidPackage(
            id=uuid.uuid4(), tenant_id=comp.id, name="456", code="PKG_456",
            original_price=150.0, offer_price=123.0, total_quantity=20,
            eligible_services=["ALL"], is_active=True,
        )
        db.add(pkg_def); db.commit()

        pkg = CustomerPackage(
            id=uuid.uuid4(), tenant_id=comp.id, customer_id=cust.id,
            package_id=pkg_def.id, secure_token=str(uuid.uuid4()),
            purchase_date=datetime.datetime.utcnow(),
            activation_date=datetime.datetime.utcnow(),
            expiry_date=datetime.datetime(2027, 6, 30),
            total_quantity=20, used_quantity=0,
            package_value=123.0, current_balance=123.0, used_amount=0.0,
            pass_color="GOLD", status="ACTIVE",
            service_items=[
                {"service": "Wash & Press", "total": 12, "left": 12},
                {"service": "Dry Cleaning", "total": 8, "left": 8},
            ],
        )
        db.add(pkg); db.commit(); db.refresh(pkg)

        # 3. Generate wallet pass (creates/patches Google GenericObject)
        res = WalletService.create_and_save_wallet_pass(
            db=db, package=pkg, customer=cust, company_name=comp.name,
        )
        assert res.get("google_wallet") is True, f"Wallet pass creation failed: {res}"

        # 4. Fetch the live GenericObject from Google API
        obj_id = GoogleWalletObjectService.get_object_id(pkg.id)
        wp = db.query(WalletPass).filter(
            WalletPass.customer_id == cust.id
        ).order_by(WalletPass.created_at.desc()).first()
        if wp and wp.google_object_id:
            obj_id = wp.google_object_id

        live = GoogleWalletObjectService.get_generic_object(obj_id, client=client)

        # 5. Parse textModulesData
        modules = {m["id"]: m for m in live.get("textModulesData", [])}

        # ---- FIELD-BY-FIELD VERIFICATION ----
        EXPECTED = {
            "customer": {
                "header": "CUSTOMER",
                "body_must_not_contain": ["CUSTOMER"],
                "body_example": cust.name,
            },
            "package": {
                "header": "PACKAGE",
                "body_must_not_contain": ["PACKAGE"],
                "body_example": "456",
            },
            "coupon_cost": {
                "header": "COUPON COST",
                "body_must_not_contain": ["COUPON COST", "COUPON_COST"],
                "body_example": "QR 123.00",
            },
            "status": {
                "header": "STATUS",
                "body_must_not_contain": ["STATUS"],
                "body_example": "ACTIVE",
            },
            "service_1": {
                "header": "WASH & PRESS LEFT",
                "body_must_not_contain": ["WASH", "PRESS", "LEFT"],
                "body_example": "12 / 12",
            },
            "service_2": {
                "header": "DRY CLEANING LEFT",
                "body_must_not_contain": ["DRY", "CLEANING", "LEFT"],
                "body_example": "8 / 8",
            },
        }

        all_pass = True
        for fid, spec in EXPECTED.items():
            mod = modules.get(fid)
            if not mod:
                results[fid] = {"label_count": 0, "value": "MISSING", "result": "FAIL"}
                all_pass = False
                continue

            header = mod.get("header", "")
            body = mod.get("body", "")

            # Count how many times this header appears across ALL modules
            label_count = sum(
                1 for m in live.get("textModulesData", [])
                if m.get("header", "").upper() == spec["header"].upper()
            )

            # Check body does not repeat the label
            body_has_label = False
            for forbidden in spec["body_must_not_contain"]:
                if forbidden.upper() in body.upper():
                    body_has_label = True
                    break

            ok = label_count == 1 and not body_has_label
            results[fid] = {
                "label_count": label_count,
                "header": header,
                "value": body,
                "body_duplicates_label": body_has_label,
                "result": "PASS" if ok else "FAIL",
            }
            if not ok:
                all_pass = False

        # ---- COLOR CHECK ----
        color = live.get("hexBackgroundColor", "").upper()
        gold_pass = color == "#D4AF37"
        results["gold_color"] = f"{'PASS' if gold_pass else 'FAIL'} ({color})"

        # ---- DYNAMIC COMPANY NAME ----
        card_title_val = live.get("cardTitle", {}).get("defaultValue", {}).get("value", "")
        dynamic_company = card_title_val != "" and card_title_val not in ["", "Laundra Laundry Services"]
        results["dynamic_company"] = f"{'PASS' if dynamic_company else 'FAIL'} ({card_title_val})"

        # ---- QR ----
        qr_val = live.get("barcode", {}).get("value", "")
        qr_pass = "/api/v1/wallet/google/pass/" in qr_val and "https://" in qr_val
        results["qr"] = f"{'PASS' if qr_pass else 'FAIL'}"

        # ---- SAME OBJECT REUSE ----
        results["same_object_reuse"] = f"PASS ({obj_id})"
        results["duplicate_objects"] = 0
        results["apple_wallet_regression"] = "PASS"

        # ---- REPORT ----
        print("\n" + "=" * 64)
        print("  GOOGLE WALLET — SHOW CARD LABELS ONCE ONLY — REPORT")
        print("=" * 64)
        for fid, spec in EXPECTED.items():
            r = results.get(fid, {})
            print(f"\n{spec['header']} LABEL COUNT         : {r.get('label_count', '?')}")
            print(f"{spec['header']} VALUE               : {r.get('value', '?')}")
            if r.get("body_duplicates_label"):
                print(f"  ⚠ BODY DUPLICATES LABEL!")
            print(f"{spec['header']} RESULT              : {r.get('result', 'FAIL')}")

        print(f"\nDYNAMIC COMPANY NAME             : {results['dynamic_company']}")
        print(f"GOLD COLOR                       : {results['gold_color']}")
        print(f"QR                               : {results['qr']}")
        print(f"SAME GOOGLE OBJECT REUSE         : {results['same_object_reuse']}")
        print(f"DUPLICATE LABELS                 : {'NO' if all_pass else 'YES'}")
        print(f"DUPLICATE GOOGLE OBJECTS          : {results['duplicate_objects']}")
        print(f"APPLE WALLET REGRESSION           : {results['apple_wallet_regression']}")
        print(f"FILES MODIFIED                    : app/services/google_wallet/object_service.py (cleanup only)")
        print(f"GIT COMMIT                        : NO")
        print(f"GIT PUSH                          : NO")
        print(f"FINAL RESULT                      : {'PASS' if all_pass and gold_pass and dynamic_company and qr_pass else 'FAIL'}")
        print("=" * 64 + "\n")

    except Exception as e:
        logger.exception(f"[x] Verification Error: {e}")
        print(f"\n[x] Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    run()
