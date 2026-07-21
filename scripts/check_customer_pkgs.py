import uuid
from app.core.database import SessionLocal
from app.models.customer_package import CustomerPackage
from app.models.user import User

def main():
    db = SessionLocal()
    cust_id = "6adbdf18-4621-40c5-b446-13c275b4189e"
    print(f"Checking Customer ID: {cust_id}")
    
    user = db.query(User).filter(User.id == cust_id).first()
    if user:
        print(f"Found User: {user.name} | Phone: {user.phone} | Role: {user.role}")
    else:
        print("User NOT found in DB by UUID!")

    all_users = db.query(User).all()
    print(f"Total Users in DB: {len(all_users)}")
    for u in all_users[:10]:
        print(f"  - User ID: {u.id} | Name: {u.name} | Email: {u.email}")

    pkgs = db.query(CustomerPackage).all()
    print(f"\nTotal CustomerPackages in DB: {len(pkgs)}")
    for p in pkgs:
        print(f"  - Pkg ID: {p.id} | Cust ID: {p.customer_id} | Status: {p.status} | Balance: {p.current_balance} | Google URL: {p.google_wallet_url[:40] if p.google_wallet_url else 'NONE'}")

if __name__ == "__main__":
    main()
