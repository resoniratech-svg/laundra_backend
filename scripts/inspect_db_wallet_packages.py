import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import SessionLocal
from app.models.customer_package import CustomerPackage
from app.models.wallet_pass import WalletPass
from app.models.user import User

def inspect():
    db = SessionLocal()
    try:
        pkgs = db.query(CustomerPackage).order_by(CustomerPackage.purchase_date.desc()).limit(10).all()
        print(f"--- Top 10 Customer Packages ---")
        for p in pkgs:
            print(f"ID: {p.id}")
            print(f"  Customer ID      : {p.customer_id}")
            print(f"  Secure Token     : {p.secure_token}")
            print(f"  Status           : {p.status}")
            print(f"  Google Wallet URL: {p.google_wallet_url}")
            print(f"  Purchase Date    : {p.purchase_date}")

            # Check matching WalletPass
            wps = db.query(WalletPass).filter(
                (WalletPass.customer_package_id == p.id) | (WalletPass.customer_id == p.customer_id)
            ).all()
            for wp in wps:
                print(f"    WalletPass ID         : {wp.id}")
                print(f"      WP customer_pkg_id  : {wp.customer_package_id}")
                print(f"      WP serial_number    : {wp.serial_number}")
                print(f"      WP google_object_id : {wp.google_object_id}")
                print(f"      WP google_wallet_url: {wp.google_wallet_url}")
            print("-" * 50)
    finally:
        db.close()

if __name__ == "__main__":
    inspect()
