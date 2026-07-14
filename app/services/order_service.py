from sqlalchemy.orm import Session
from uuid import UUID, uuid4
from datetime import datetime, date
from decimal import Decimal
import random
import string
from fastapi import HTTPException, status

from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.customer import Customer
from app.models.service import Service
from app.models.coupon import Coupon
from app.core.tenant import get_current_tenant_id

class OrderService:
    @staticmethod
    def generate_order_number() -> str:
        return str(random.randint(100000, 999999))

    @staticmethod
    def create_order(
        db: Session,
        *,
        customer_id: UUID,
        items_in: list,
        coupon_code: str = None,
        tenant_id: UUID = None
    ) -> Order:
        if not tenant_id:
            tenant_id = get_current_tenant_id()
        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant context not found"
            )

        # 1. Verify customer
        customer = db.query(Customer).filter(
            Customer.id == customer_id, 
            Customer.tenant_id == tenant_id
        ).first()
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found"
            )

        # 2. Process order items & calculate total amount
        total_amount = Decimal("0.0")
        items_to_create = []
        
        for item in items_in:
            service = db.query(Service).filter(
                Service.id == item.service_id, 
                Service.tenant_id == tenant_id
            ).first()
            if not service:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Service not found: {item.service_id}"
                )
            
            item_total = service.price * item.quantity
            total_amount += item_total
            
            order_item = OrderItem(
                id=uuid4(),
                service_id=service.id,
                quantity=item.quantity,
                price=service.price
            )
            items_to_create.append(order_item)

        # 3. Handle Coupon
        discount = Decimal("0.0")
        if coupon_code:
            coupon = db.query(Coupon).filter(
                Coupon.code == coupon_code,
                Coupon.tenant_id == tenant_id
            ).first()
            
            if not coupon:
                 raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Invalid coupon code"
                )
            
            # Check expiry
            if coupon.expiry_date and coupon.expiry_date < date.today():
                 raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Coupon has expired"
                )
            
            if coupon.discount_type == "PERCENTAGE":
                discount = total_amount * (coupon.value / Decimal("100.0"))
            elif coupon.discount_type == "FLAT":
                discount = coupon.value
            
            # Ensure discount doesn't exceed total amount
            discount = min(discount, total_amount)

        final_amount = total_amount - discount

        # 4. Create Order
        order_id = uuid4()
        order = Order(
            id=order_id,
            tenant_id=tenant_id,
            customer_id=customer_id,
            order_number=OrderService.generate_order_number(),
            status="CREATED",
            total_amount=final_amount,
            discount=discount,
            paid_amount=Decimal("0.0"),
            payment_status="UNPAID",
            qr_code=f"https://laundrysaas.com/orders/{order_id}/qr"
        )
        db.add(order)
        db.flush()

        # 5. Save items
        for order_item in items_to_create:
            order_item.order_id = order_id
            db.add(order_item)

        # 6. Update loyalty points (+1 point per 100 spent)
        points_earned = int(final_amount // Decimal("100.0"))
        customer.loyalty_points += points_earned
        
        db.commit()
        db.refresh(order)
        return order
