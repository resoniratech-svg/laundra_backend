from sqlalchemy.orm import Session
from sqlalchemy import text
from uuid import UUID, uuid4
from decimal import Decimal
from datetime import date

from app.core.database import SessionLocal, engine
from app.models.base import Base
from app.models.company import Company
from app.models.user import User
from app.models.customer import Customer
from app.models.service import Service
from app.models.order import Order
from app.models.coupon import Coupon
from app.models.subscription import Subscription
from app.core.tenant import set_current_tenant_id
from app.services.auth_service import AuthService
from app.services.order_service import OrderService
from app.services.payment_service import PaymentService
from app.services.delivery_service import DeliveryService
from app.core.security import get_password_hash

def clean_database(db: Session):
    print("Cleaning database tables...")
    db.execute(text("TRUNCATE TABLE deliveries, payments, order_items, orders, services, coupons, expenses, customers, users, companies, subscriptions, support_tickets, company_features, platform_settings, announcements, attendance, leave_requests CASCADE"))
    db.commit()

def run_seeding_and_verification():
    db = SessionLocal()
    
    try:
        clean_database(db)
    except Exception as e:
        print(f"Truncation error: {e}. Proceeding with inserting new records.")
        db.rollback()

    print("\n--- Seeding Tenant A (Bubble Wash) ---")
    co_a, admin_a = AuthService.register_company(
        db,
        company_name="Bubble Wash",
        phone="9876543210",
        email="admin@bubblewash.com",
        password="password123"
    )
    print(f"Company A created: {co_a.name} (ID: {co_a.id})")
    print(f"Admin A created: {admin_a.email}")
    
    # 1. Seed Super Admin
    super_admin = User(
        id=uuid4(),
        tenant_id=co_a.id,
        name="Platform Super Admin",
        phone="9999999999",
        email="superadmin@laundrysaas.com",
        password=get_password_hash("superpassword"),
        role="SUPER_ADMIN",
        status="ACTIVE"
    )
    db.add(super_admin)
    db.commit()
    print(f"Super Admin seeded: {super_admin.email}")

    # Set context to Tenant A
    set_current_tenant_id(co_a.id)

    # 2. Seed Customer (User & Customer Table sharing same UUID)
    cust_id = uuid4()
    cust_user = User(
        id=cust_id,
        tenant_id=co_a.id,
        name="John Doe",
        phone="8888888888",
        email="john@gmail.com",
        password=get_password_hash("john123"),
        role="CUSTOMER",
        status="ACTIVE"
    )
    db.add(cust_user)
    db.commit()

    customer_a = Customer(
        id=cust_id,
        tenant_id=co_a.id,
        name="John Doe",
        phone="8888888888",
        email="john@gmail.com",
        wallet_balance=Decimal("500.0"),
        loyalty_points=100
    )
    db.add(customer_a)
    db.commit()
    print(f"Customer John Doe seeded: {customer_a.email}")

    # 3. Seed Delivery Boy
    db_id = uuid4()
    delivery_boy = User(
        id=db_id,
        tenant_id=co_a.id,
        name="Bob Delivery",
        phone="9998887777",
        email="delivery@bubblewash.com",
        password=get_password_hash("delivery123"),
        role="DELIVERY_BOY",
        status="ACTIVE",
        vehicle_type="BIKE",
        vehicle_number="AB-12-CD-3456"
    )
    db.add(delivery_boy)
    db.commit()
    print(f"Delivery Boy Bob seeded: {delivery_boy.email}")

    # Create Service for Company A
    service_a = Service(
        id=uuid4(),
        tenant_id=co_a.id,
        name="Dry Clean",
        category="Premium",
        price=Decimal("150.0"),
        unit="PIECE"
    )
    db.add(service_a)
    db.commit()
    print(f"Service A created: {service_a.name} at {service_a.price} per {service_a.unit}")

    # Place Order for Customer A
    class DummyItem:
        def __init__(self, service_id, quantity):
            self.service_id = service_id
            self.quantity = quantity

    order_a = OrderService.create_order(
        db,
        customer_id=customer_a.id,
        items_in=[DummyItem(service_a.id, 2)]
    )
    print(f"Order A created for Tenant A: {order_a.order_number} (Total: {order_a.total_amount})")

    # Record Payment for Order A
    PaymentService.create_payment(
        db,
        order_id=order_a.id,
        amount=Decimal("300.0"),
        method="CASH"
    )
    print(f"Payment recorded. Order A paid amount: {order_a.paid_amount}, payment status: {order_a.payment_status}")


    print("\n--- Seeding Tenant B (Iron Press) ---")
    co_b, admin_b = AuthService.register_company(
        db,
        company_name="Iron Press",
        phone="7654321098",
        email="admin@ironpress.com",
        password="password456"
    )
    print(f"Company B created: {co_b.name} (ID: {co_b.id})")
    print(f"Admin B created: {admin_b.email}")

    # Create Service for Company B
    set_current_tenant_id(co_b.id)
    service_b = Service(
        id=uuid4(),
        tenant_id=co_b.id,
        name="Steam Ironing",
        category="Express",
        price=Decimal("20.0"),
        unit="PIECE"
    )
    db.add(service_b)
    db.commit()
    print(f"Service B created: {service_b.name} at {service_b.price} per {service_b.unit}")

    # Create Customer for Company B
    customer_b = Customer(
        id=uuid4(),
        tenant_id=co_b.id,
        name="Jane Smith",
        phone="7777777777",
        email="jane@gmail.com",
        wallet_balance=Decimal("100.0"),
        loyalty_points=0
    )
    db.add(customer_b)
    db.commit()
    print(f"Customer B created: {customer_b.name}")

    # Place Order for Company B
    order_b = OrderService.create_order(
        db,
        customer_id=customer_b.id,
        items_in=[DummyItem(service_b.id, 5)]
    )
    print(f"Order B created for Tenant B: {order_b.order_number} (Total: {order_b.total_amount})")


    print("\n--- Tenant Isolation Verification ---")
    
    from app.repositories.order_repository import OrderRepository
    order_repo = OrderRepository()

    # Step 3.1: Set context to Tenant A
    set_current_tenant_id(co_a.id)
    print(f"Current tenant context set to Company A (Bubble Wash: {co_a.id})")
    
    fetched_a = order_repo.get(db, order_a.id)
    print(f"Fetching Order A under Tenant A context: {'SUCCESS' if fetched_a else 'FAILED'}")
    assert fetched_a is not None, "Tenant A should be able to view Order A"

    fetched_b_under_a = order_repo.get(db, order_b.id)
    print(f"Fetching Order B under Tenant A context: {'FOUND (FAIL - LEAKED!)' if fetched_b_under_a else 'NOT FOUND (SUCCESS - ISOLATED!)'}")
    assert fetched_b_under_a is None, "Tenant A should NOT be able to view Order B due to tenant isolation!"

    # Step 3.2: Set context to Tenant B
    set_current_tenant_id(co_b.id)
    print(f"Current tenant context set to Company B (Iron Press: {co_b.id})")
    
    fetched_b = order_repo.get(db, order_b.id)
    print(f"Fetching Order B under Tenant B context: {'SUCCESS' if fetched_b else 'FAILED'}")
    assert fetched_b is not None, "Tenant B should be able to view Order B"

    fetched_a_under_b = order_repo.get(db, order_a.id)
    print(f"Fetching Order A under Tenant B context: {'FOUND (FAIL - LEAKED!)' if fetched_a_under_b else 'NOT FOUND (SUCCESS - ISOLATED!)'}")
    assert fetched_a_under_b is None, "Tenant B should NOT be able to view Order A due to tenant isolation!"

    print("\n[SUCCESS] Verification COMPLETE: Multi-tenant data isolation holds successfully!")
    db.close()

if __name__ == "__main__":
    run_seeding_and_verification()
