from sqlalchemy.orm import Session
from uuid import UUID, uuid4
from decimal import Decimal
from fastapi import HTTPException, status
from app.models.payment import Payment
from app.models.order import Order
from app.models.customer import Customer
from app.core.tenant import get_current_tenant_id

class PaymentService:
    @staticmethod
    def create_payment(
        db: Session,
        order_id: UUID,
        amount: Decimal,
        method: str,
        delivery_boy_id: UUID = None,
        delivery_boy_commission: Decimal = None,
        tenant_id: UUID = None
    ) -> Payment:
        if not tenant_id:
            tenant_id = get_current_tenant_id()
        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant context not found"
            )

        # 1. Fetch order
        order = db.query(Order).filter(
            Order.id == order_id,
            Order.tenant_id == tenant_id
        ).first()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )

        # 2. Check remaining amount
        remaining = order.total_amount - order.paid_amount
        if amount > remaining:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Payment amount ({amount}) exceeds remaining balance ({remaining})"
            )

        # 3. Handle Wallet deduction
        if method == "WALLET":
            customer = db.query(Customer).filter(
                Customer.id == order.customer_id,
                Customer.tenant_id == tenant_id
            ).first()
            if not customer:
                 raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Customer not found"
                )
            
            if customer.wallet_balance < amount:
                 raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient wallet balance. Current: {customer.wallet_balance}"
                )
            customer.wallet_balance -= amount

        # Calculate commission for CASH payments
        if method == "CASH" and delivery_boy_id and delivery_boy_commission is None:
            from app.models.company import Company
            company = db.query(Company).filter(Company.id == tenant_id).first()
            if company and company.delivery_commission_percent:
                percent = Decimal(str(company.delivery_commission_percent))
                delivery_boy_commission = amount * (percent / Decimal('100.0'))

        # 4. Create Payment record
        payment = Payment(
            id=uuid4(),
            tenant_id=tenant_id,
            order_id=order_id,
            amount=amount,
            method=method,
            status="SUCCESS",
            delivery_boy_id=delivery_boy_id,
            delivery_boy_commission=delivery_boy_commission
        )
        db.add(payment)

        # 5. Update Order paid status
        order.paid_amount += amount
        if order.paid_amount >= order.total_amount:
            order.payment_status = "PAID"
        elif order.paid_amount > 0:
            order.payment_status = "PARTIALLY_PAID"
        else:
            order.payment_status = "UNPAID"

        db.commit()
        db.refresh(payment)
        return payment
