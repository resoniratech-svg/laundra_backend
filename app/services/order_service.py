from sqlalchemy.orm import Session
from uuid import UUID, uuid4
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
import random
import string
from fastapi import HTTPException, status

from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.customer import Customer
from app.models.service import Service
from app.models.coupon import Coupon
from app.models.customer_package import CustomerPackage
from app.services.wallet_service import WalletService
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
        tenant_id: UUID = None,
        is_express: bool = False,
        pay_with_package_id: UUID = None,
        pickup_address: str = None,
        delivery_address: str = None,
        special_instructions: str = None,
        pickup_date: datetime = None,
        payment_status: str = None,
        payment_method: str = None,
        paid_amount: Decimal = None,
        total_amount: Decimal = None,
        discount: Decimal = None,
        order_number: str = None
    ) -> Order:
        if not tenant_id:
            tenant_id = get_current_tenant_id()
        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant context not found"
            )

        # 1. Verify customer (flexible lookup by UUID, phone, or name)
        customer = None
        try:
            from uuid import UUID as PyUUID
            cust_uuid = PyUUID(str(customer_id))
            customer = db.query(Customer).filter(
                Customer.id == cust_uuid, 
                Customer.tenant_id == tenant_id
            ).first()
        except Exception:
            pass

        if not customer and customer_id:
            customer = db.query(Customer).filter(
                Customer.phone == str(customer_id),
                Customer.tenant_id == tenant_id
            ).first()

        if not customer and customer_id:
            customer = db.query(Customer).filter(
                Customer.name.ilike(f"%{str(customer_id)}%"),
                Customer.tenant_id == tenant_id
            ).first()

        if not customer:
            # Fallback to first customer or create on the fly
            customer = db.query(Customer).filter(Customer.tenant_id == tenant_id).first()
            if not customer:
                customer = Customer(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    name="Field Customer",
                    phone="N/A",
                    address="Doorstep Pickup",
                    wallet_balance=Decimal("0.0"),
                    loyalty_points=0
                )
                db.add(customer)
                db.commit()
                db.refresh(customer)

        # Default addresses to customer address if not explicitly passed
        final_pickup_address = pickup_address or getattr(customer, 'address', None) or 'Pickup at Branch'
        final_delivery_address = delivery_address or getattr(customer, 'address', None) or 'Delivery at Branch'

        # Check for existing order by order_number (Idempotent Deduplication)
        if order_number:
            clean_num = str(order_number).replace('#', '').strip()
            existing_order = db.query(Order).filter(
                Order.order_number == clean_num,
                Order.tenant_id == tenant_id
            ).first()
            if existing_order:
                if payment_status and str(payment_status).upper() in ["PAID", "COMPLETED"]:
                    existing_order.payment_status = "PAID"
                    if paid_amount is not None:
                        existing_order.paid_amount = Decimal(str(paid_amount))
                db.commit()
                db.refresh(existing_order)
                return existing_order

        # 2. Process order items & calculate total amount
        calculated_total = Decimal("0.0")
        items_to_create = []
        
        for item in items_in:
            service = None
            try:
                from uuid import UUID as PyUUID
                srv_uuid = PyUUID(str(item.service_id))
                service = db.query(Service).filter(
                    Service.id == srv_uuid, 
                    Service.tenant_id == tenant_id
                ).first()
            except Exception:
                pass

            if not service:
                service = db.query(Service).filter(
                    Service.tenant_id == tenant_id
                ).first()

            if not service:
                service = Service(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    name="Standard Laundry",
                    price=Decimal("10.0"),
                    category="General"
                )
                db.add(service)
                db.commit()
                db.refresh(service)
            
            # Use explicit item price if provided by POS/caller, else fallback to service master price
            item_price = getattr(item, 'price', None) if getattr(item, 'price', None) is not None else getattr(item, 'unit_price', None)
            if item_price is not None:
                price = Decimal(str(item_price))
            else:
                price = service.express_price if (is_express and service.express_price is not None) else service.price
            item_total = price * item.quantity
            calculated_total += item_total
            
            order_item = OrderItem(
                id=uuid4(),
                service_id=service.id,
                quantity=item.quantity,
                price=price,
                ordered_quantity=item.quantity,
                picked_up_quantity=0,
                pickup_pending_quantity=item.quantity,
                delivered_quantity=0,
                delivery_pending_quantity=0,
                item_status="CREATED"
            )
            items_to_create.append(order_item)

        # 3. Handle Coupon & Discount
        calculated_discount = Decimal("0.0")
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
                calculated_discount = calculated_total * (coupon.value / Decimal("100.0"))
            elif coupon.discount_type == "FLAT":
                calculated_discount = coupon.value
            
            # Ensure discount doesn't exceed total amount
            calculated_discount = min(calculated_discount, calculated_total)

        # 4. Determine Final Total Amount
        if total_amount is not None:
            final_amount = Decimal(str(total_amount))
            final_discount = Decimal(str(discount)) if discount is not None else calculated_discount
        else:
            final_discount = calculated_discount
            final_amount = max(Decimal("0.0"), calculated_total - final_discount)

        # 5. Create Order
        order_id = uuid4()
        
        # Calculate initial payment status & paid amount
        computed_payment_status = "UNPAID"
        computed_paid_amount = Decimal("0.0")
        
        if payment_status and str(payment_status).upper() in ["PAID", "COMPLETED"]:
            computed_payment_status = "PAID"
            computed_paid_amount = final_amount if paid_amount is None else Decimal(str(paid_amount))
        elif paid_amount and Decimal(str(paid_amount)) >= final_amount and final_amount > 0:
            computed_payment_status = "PAID"
            computed_paid_amount = Decimal(str(paid_amount))

        order = Order(
            id=order_id,
            tenant_id=tenant_id,
            customer_id=customer_id,
            order_number=str(order_number) if order_number else OrderService.generate_order_number(),
            status="CREATED",
            total_amount=final_amount,
            discount=final_discount,
            paid_amount=computed_paid_amount,
            payment_status=computed_payment_status,
            payment_method=payment_method or "CASH",
            pickup_payment_method=payment_method or "CASH",
            qr_code=f"https://laundrysaas.com/orders/{order_id}/qr",
            is_express=is_express,
            applied_package_id=pay_with_package_id,
            pickup_address=final_pickup_address,
            delivery_address=final_delivery_address,
            special_instructions=special_instructions,
            pickup_date=pickup_date or datetime.utcnow()
        )
        db.add(order)
        db.flush()

        # Deduct from Prepaid Package Wallet if selected
        if pay_with_package_id:
            pkg = db.query(CustomerPackage).filter(
                CustomerPackage.id == pay_with_package_id,
                CustomerPackage.customer_id == customer_id,
                CustomerPackage.tenant_id == tenant_id
            ).first()
            if not pkg:
                raise HTTPException(status_code=404, detail="Selected prepaid package not found")
            if pkg.current_balance < final_amount:
                raise HTTPException(status_code=400, detail="Insufficient balance in prepaid package")
            
            pkg.current_balance = float(Decimal(str(pkg.current_balance)) - final_amount)
            pkg.used_amount = float(Decimal(str(pkg.used_amount)) + final_amount)
            pkg.pass_color = WalletService.update_pass_color(pkg)
            if pkg.current_balance <= 0:
                pkg.status = "COMPLETED"
            else:
                pkg.status = "IN_USE"
                
            order.paid_amount = final_amount
            order.payment_status = "PAID"
            
            # Automatically update & regenerate Apple Wallet PKPass
            try:
                WalletService.update_wallet_pass_on_usage(db, pkg, customer)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to auto-update wallet pass on order completion: {e}")


        # 5. Save items
        for order_item in items_to_create:
            order_item.order_id = order_id
            db.add(order_item)

        # 6. Update loyalty points (+1 point per 100 spent)
        db.commit()
        db.refresh(order)
        return order

    @staticmethod
    def create_package_deduction_order(
        db: Session,
        *,
        customer_package: CustomerPackage,
        tenant_id: UUID,
        customer_id: UUID,
        amount_deducted: float = 0.0,
        deductions: list = None,
        remarks: str = None
    ) -> Optional[Order]:
        """
        Creates a completed Order History record for a prepaid package deduction.
        This record appears in the Order History Archive module without disturbing wallet or package calculations.
        """
        try:
            order_id = uuid4()
            order_num = OrderService.generate_order_number()
            now = datetime.utcnow()

            deductions_list = deductions or []
            order_total = Decimal(str(amount_deducted)) if amount_deducted and amount_deducted > 0 else Decimal("0.0")

            # Format special instructions / remarks summary
            summary_parts = []
            for d in deductions_list:
                qty = getattr(d, "quantity", 0)
                svc = getattr(d, "service", "Service")
                if qty > 0:
                    summary_parts.append(f"{qty}x {svc}")
            if amount_deducted and amount_deducted > 0:
                summary_parts.append(f"QR {amount_deducted:.2f} Wallet")

            ded_summary = ", ".join(summary_parts) if summary_parts else "Package Deduction"
            order_remarks = remarks or f"Package Deduction ({ded_summary})"

            # Create Order Header
            order = Order(
                id=order_id,
                tenant_id=tenant_id,
                customer_id=customer_id,
                order_number=order_num,
                status="Completed",
                total_amount=order_total,
                discount=Decimal("0.0"),
                paid_amount=order_total,
                payment_status="PAID",
                applied_package_id=customer_package.id,
                special_instructions=order_remarks,
                pickup_date=now,
                delivery_date=now,
                qr_code=f"https://laundrysaas.com/orders/{order_id}/qr"
            )
            db.add(order)
            db.flush()

            # Create OrderItems for services/cloths actually deducted (quantity > 0)
            for ded in deductions_list:
                qty = getattr(ded, "quantity", 0)
                svc_name = getattr(ded, "service", "")
                if qty <= 0 or not svc_name:
                    continue

                clean_svc_name = svc_name.strip()

                # 1. Lookup matching Service record in DB by exact/ilike name first (Cloth/garment name)
                service = db.query(Service).filter(
                    Service.tenant_id == tenant_id,
                    Service.name.ilike(clean_svc_name)
                ).first()

                # 2. If not matched by Service name, try matching by Service category
                if not service:
                    service = db.query(Service).filter(
                        Service.tenant_id == tenant_id,
                        Service.category.ilike(clean_svc_name)
                    ).first()

                # 3. Fallback to any service in tenant if still not matched
                if not service:
                    service = db.query(Service).filter(Service.tenant_id == tenant_id).first()

                if service:
                    order_item = OrderItem(
                        id=uuid4(),
                        order_id=order_id,
                        service_id=service.id,
                        quantity=qty,
                        price=Decimal("0.0"),
                        ordered_quantity=qty,
                        picked_up_quantity=qty,
                        pickup_pending_quantity=0,
                        delivered_quantity=qty,
                        delivery_pending_quantity=0,
                        item_status="COMPLETED"
                    )
                    # Dynamically set exact cloth name on item instance
                    setattr(order_item, 'service_name', clean_svc_name if clean_svc_name else service.name)
                    db.add(order_item)

            db.commit()
            db.refresh(order)
            return order

        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error creating package deduction Order History: {e}")
            db.rollback()
            return None
