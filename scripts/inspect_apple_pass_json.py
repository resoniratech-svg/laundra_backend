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
from app.services.apple_wallet.pass_service import PassService as ApplePassService, LaundryPassData

logging.basicConfig(level=logging.INFO)

def inspect_pass():
    db = SessionLocal()
    try:
        customer = db.query(User).filter(User.name.isnot(None)).first()
        company = db.query(Company).first()

        assert customer is not None, "Customer not found"
        assert company is not None, "Company not found"

        # 9 Services matching the user's screenshot (LUXX package for manjith)
        items = [
            {"service": "Pressing", "total": 7, "left": 7},
            {"service": "Wash & Press", "total": 7, "left": 7},
            {"service": "Dry Cleaning", "total": 6, "left": 6},
            {"service": "Premium Services", "total": 7, "left": 7},
            {"service": "Wash & Fold", "total": 8, "left": 8},
            {"service": "Steam Press", "total": 7, "left": 7},
            {"service": "Hotel Laundry", "total": 6, "left": 6},
            {"service": "Commercial Laundry", "total": 12, "left": 12},
            {"service": "Express Services", "total": 11, "left": 11}
        ]

        pass_data = LaundryPassData(
            company_name="iron",
            customer_name="manjith",
            package_name="LUXX",
            package_id="PASS-LUXX-999",
            remaining_balance="500.00",
            coupon_cost="QR 500.00",
            expiry_date="31 Aug 2026",
            qr_data="https://example.com/verify",
            service_items=items
        )

        apple_service = ApplePassService()
        pass_json_path = apple_service.generate(pass_data, serial_number="TEST-LUXX-001")

        with open(pass_json_path, "r", encoding="utf-8") as f:
            pass_dict = json.load(f)

        print("\n" + "="*80)
        print("  FULL GENERATED APPLE WALLET pass.json (UNTRUNCATED)")
        print("="*80)
        print(json.dumps(pass_dict, indent=2))
        print("="*80 + "\n")

    finally:
        db.close()

if __name__ == "__main__":
    inspect_pass()
