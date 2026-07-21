import uuid
from app.core.database import SessionLocal
from app.models.customer_package import CustomerPackage
from app.models.user import User
from app.services.wallet_service import WalletService

def main():
    db = SessionLocal()
    cust_id = "6adbdf18-4621-40c5-b446-13c275b4189e"
    customer = db.query(User).filter(User.id == cust_id).first()
    if not customer:
        print("Customer charan not found")
        return

    pkgs = db.query(CustomerPackage).filter(
        CustomerPackage.customer_id == cust_id,
        CustomerPackage.status == "ACTIVE"
    ).all()

    print(f"Updating {len(pkgs)} active packages for customer {customer.name}...")
    for p in pkgs:
        new_url = WalletService.create_and_save_wallet_pass(
            db=db,
            package=p,
            customer=customer,
            company_name="Laundra Laundry"
        )
        print(f"\nUPDATED PKG {p.id}:")
        print(f"NEW GOOGLE WALLET URL:\n{new_url}\n")

if __name__ == "__main__":
    main()
