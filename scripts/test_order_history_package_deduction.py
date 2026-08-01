import os
import sys
import uuid
import datetime

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logging
from app.core.database import SessionLocal
from app.models.customer_package import CustomerPackage
from app.models.user import User
from app.models.company import Company
from app.models.prepaid_package import PrepaidPackage
from app.models.order import Order
from app.models.order_item import OrderItem
from app.schemas.prepaid_package import CustomerPackageDeductRequest, ServiceDeduction
from app.api.v1.prepaid_packages import deduct_package_usage

logging.basicConfig(level=logging.INFO)

def test_package_deduction_order_history():
    db = SessionLocal()
    try:
        customer = db.query(User).filter(User.name.isnot(None)).first()
        company = db.query(Company).first()
        pkg_def = db.query(PrepaidPackage).first()

        assert customer is not None, "Customer missing"
        assert company is not None, "Company missing"

        pkg_id = pkg_def.id if pkg_def else uuid.uuid4()

        print("\n" + "="*75)
        print("  VERIFYING AUTOMATIC ORDER HISTORY CREATION FOR PACKAGE DEDUCTIONS")
        print("="*75)

        # 1. Create a test CustomerPackage with 3 services
        items = [
            {"service": "Pressing", "total": 10, "left": 10},
            {"service": "Wash & Press", "total": 5, "left": 5},
            {"service": "Dry Cleaning", "total": 4, "left": 4}
        ]

        cp = CustomerPackage(
            id=uuid.uuid4(),
            tenant_id=company.id,
            customer_id=customer.id,
            package_id=pkg_id,
            purchase_date=datetime.datetime.utcnow(),
            total_quantity=19,
            package_value=200.0,
            current_balance=200.0,
            status="ACTIVE",
            secure_token=str(uuid.uuid4()),
            service_items=items
        )
        db.add(cp)
        db.commit()
        db.refresh(cp)

        print(f"\n[+] Created test CustomerPackage ID: {cp.id} for Customer '{customer.name}'")

        # 2. Perform Deduction: 2x Pressing, 1x Wash & Press, 0x Dry Cleaning, QR 25.00 Wallet
        deduct_req = CustomerPackageDeductRequest(
            customer_package_id=cp.id,
            customer_id=customer.id,
            amount_used=25.0,
            remarks="Staff deduction test for Order History Archive",
            deductions=[
                ServiceDeduction(service="Pressing", quantity=2),
                ServiceDeduction(service="Wash & Press", quantity=1),
                ServiceDeduction(service="Dry Cleaning", quantity=0)
            ]
        )

        resp = deduct_package_usage(
            payload=deduct_req,
            background_tasks=None,
            db=db,
            current_user=customer
        )

        print(f"[+] Deduction API executed successfully! Remaining balance: QR {resp.current_balance}")

        # 3. Query `orders` table to verify automatic Order creation
        created_order = db.query(Order).filter(
            Order.applied_package_id == cp.id,
            Order.tenant_id == company.id
        ).first()

        assert created_order is not None, "Order History record was NOT created in 'orders' table!"
        print(f"\n[OK] Found generated Order in DB!")
        print(f"     - Order ID: {created_order.id}")
        print(f"     - Order Number: #{created_order.order_number}")
        print(f"     - Status: {created_order.status}")
        print(f"     - Payment Status: {created_order.payment_status}")
        print(f"     - Total Amount: QR {created_order.total_amount:.2f}")
        print(f"     - Applied Package ID: {created_order.applied_package_id}")
        print(f"     - Special Instructions / Remarks: {created_order.special_instructions}")

        assert created_order.status == "Completed", f"Expected status 'Completed', got '{created_order.status}'"
        assert created_order.payment_status == "Paid", f"Expected payment_status 'Paid', got '{created_order.payment_status}'"
        assert created_order.tenant_id == company.id, "Tenant isolation mismatch!"

        # 4. Query `order_items` table to verify line items (only quantity > 0)
        items_in_db = db.query(OrderItem).filter(OrderItem.order_id == created_order.id).all()
        print(f"\n[+] OrderItems created in DB: {len(items_in_db)}")
        for oi in items_in_db:
            print(f"     - OrderItem Service ID: {oi.service_id} | Qty: {oi.quantity} | Status: {oi.item_status}")

        assert len(items_in_db) == 2, f"Expected 2 OrderItems (Pressing & Wash & Press), got {len(items_in_db)}"

        print("\n" + "="*75)
        print("  AUTOMATIC ORDER HISTORY CREATION VERIFICATION PASSED 100%")
        print("="*75 + "\n")

    finally:
        db.close()

if __name__ == "__main__":
    test_package_deduction_order_history()
