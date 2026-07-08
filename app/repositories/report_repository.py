from sqlalchemy.orm import Session
from sqlalchemy import func, case
from datetime import datetime, date, timedelta
from decimal import Decimal
from uuid import UUID

from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.customer import Customer
from app.models.payment import Payment
from app.models.delivery import Delivery
from app.models.expense import Expense
from app.models.coupon import Coupon
from app.models.service import Service
from app.models.user import User

class ReportRepository:
    @staticmethod
    def get_dashboard_summary(db: Session, tenant_id: UUID) -> dict:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        thirty_days_ago = today_start - timedelta(days=30)
        
        today_orders = db.query(func.count(Order.id)).filter(
            Order.tenant_id == tenant_id, Order.created_at >= today_start
        ).scalar() or 0
        
        pending_orders = db.query(func.count(Order.id)).filter(
            Order.tenant_id == tenant_id, Order.status.notin_(["DELIVERED", "CANCELLED"])
        ).scalar() or 0
        
        completed_orders = db.query(func.count(Order.id)).filter(
            Order.tenant_id == tenant_id, Order.status == "DELIVERED"
        ).scalar() or 0
        
        today_revenue = db.query(func.sum(Payment.amount)).filter(
            Payment.tenant_id == tenant_id, Payment.status == "SUCCESS", Payment.created_at >= today_start
        ).scalar() or Decimal("0.0")
        
        monthly_revenue = db.query(func.sum(Payment.amount)).filter(
            Payment.tenant_id == tenant_id, Payment.status == "SUCCESS", Payment.created_at >= thirty_days_ago
        ).scalar() or Decimal("0.0")
        
        active_customers = db.query(func.count(func.distinct(Order.customer_id))).filter(
            Order.tenant_id == tenant_id, Order.created_at >= thirty_days_ago
        ).scalar() or 0
        
        delivery_pending = db.query(func.count(Delivery.id)).filter(
            Delivery.tenant_id == tenant_id, Delivery.status != "DELIVERED"
        ).scalar() or 0
        
        return {
            "today_orders": today_orders,
            "pending_orders": pending_orders,
            "completed_orders": completed_orders,
            "today_revenue": today_revenue,
            "monthly_revenue": monthly_revenue,
            "active_customers": active_customers,
            "delivery_pending": delivery_pending
        }

    @staticmethod
    def get_daily_sales(db: Session, tenant_id: UUID, target_date: date) -> dict:
        start_dt = datetime.combine(target_date, datetime.min.time())
        end_dt = datetime.combine(target_date, datetime.max.time())
        
        orders_count = db.query(func.count(Order.id)).filter(
            Order.tenant_id == tenant_id, Order.created_at.between(start_dt, end_dt)
        ).scalar() or 0
        
        revenue = db.query(func.sum(Payment.amount)).filter(
            Payment.tenant_id == tenant_id, Payment.status == "SUCCESS", Payment.created_at.between(start_dt, end_dt)
        ).scalar() or Decimal("0.0")
        
        avg_value = revenue / Decimal(orders_count) if orders_count > 0 else Decimal("0.0")
        
        return {
            "date": target_date.isoformat(),
            "orders": orders_count,
            "revenue": revenue,
            "average_order_value": round(avg_value, 2)
        }

    @staticmethod
    def get_monthly_sales(db: Session, tenant_id: UUID) -> dict:
        start_date = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        orders_count = db.query(func.count(Order.id)).filter(
            Order.tenant_id == tenant_id, Order.created_at >= start_date
        ).scalar() or 0
        
        revenue = db.query(func.sum(Payment.amount)).filter(
            Payment.tenant_id == tenant_id, Payment.status == "SUCCESS", Payment.created_at >= start_date
        ).scalar() or Decimal("0.0")
        
        customers_count = db.query(func.count(func.distinct(Order.customer_id))).filter(
            Order.tenant_id == tenant_id, Order.created_at >= start_date
        ).scalar() or 0
        
        return {
            "orders": orders_count,
            "revenue": revenue,
            "customers": customers_count
        }

    @staticmethod
    def get_yearly_sales(db: Session, tenant_id: UUID) -> dict:
        start_date = datetime.now().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        
        orders_count = db.query(func.count(Order.id)).filter(
            Order.tenant_id == tenant_id, Order.created_at >= start_date
        ).scalar() or 0
        
        revenue = db.query(func.sum(Payment.amount)).filter(
            Payment.tenant_id == tenant_id, Payment.status == "SUCCESS", Payment.created_at >= start_date
        ).scalar() or Decimal("0.0")
        
        customers_count = db.query(func.count(func.distinct(Order.customer_id))).filter(
            Order.tenant_id == tenant_id, Order.created_at >= start_date
        ).scalar() or 0
        
        return {
            "orders": orders_count,
            "revenue": revenue,
            "customers": customers_count
        }

    @staticmethod
    def get_orders_by_status(db: Session, tenant_id: UUID) -> dict:
        res = db.query(Order.status, func.count(Order.id)).filter(
            Order.tenant_id == tenant_id
        ).group_by(Order.status).all()
        return {row[0].lower() if row[0] else "unknown": row[1] for row in res}

    @staticmethod
    def get_orders_between_dates(db: Session, tenant_id: UUID, start: date, end: date) -> list:
        start_dt = datetime.combine(start, datetime.min.time())
        end_dt = datetime.combine(end, datetime.max.time())
        return db.query(Order).filter(
            Order.tenant_id == tenant_id, Order.created_at.between(start_dt, end_dt)
        ).all()

    @staticmethod
    def get_top_customers(db: Session, tenant_id: UUID, sort_by: str = "spent") -> list:
        query = db.query(
            Customer.id,
            Customer.name,
            Customer.phone,
            func.count(Order.id).label("total_orders"),
            func.sum(Order.total_amount).label("total_spent")
        ).join(Order, Order.customer_id == Customer.id).filter(
            Customer.tenant_id == tenant_id
        ).group_by(Customer.id)
        
        if sort_by == "orders":
            query = query.order_by(func.count(Order.id).desc())
        else:
            query = query.order_by(func.sum(Order.total_amount).desc())
            
        res = query.limit(10).all()
        return [
            {
                "id": r[0],
                "name": r[1],
                "phone": r[2],
                "total_orders": r[3],
                "total_spent": r[4] or Decimal("0.0")
            }
            for r in res
        ]

    @staticmethod
    def get_customer_growth(db: Session, tenant_id: UUID) -> list:
        res = db.query(
            func.to_char(Customer.created_at, "YYYY-MM").label("month"),
            func.count(Customer.id).label("new_customers")
        ).filter(
            Customer.tenant_id == tenant_id
        ).group_by("month").order_by("month").all()
        return [{"month": r[0], "new_customers": r[1]} for r in res]

    @staticmethod
    def get_customer_wallet_report(db: Session, tenant_id: UUID) -> list:
        res = db.query(
            Customer.id, Customer.name, Customer.phone, Customer.wallet_balance
        ).filter(
            Customer.tenant_id == tenant_id, Customer.wallet_balance > 0
        ).order_by(Customer.wallet_balance.desc()).all()
        return [
            {"id": r[0], "name": r[1], "phone": r[2], "wallet_balance": r[3]} for r in res
        ]

    @staticmethod
    def get_revenue_by_payment_method(db: Session, tenant_id: UUID) -> dict:
        res = db.query(Payment.method, func.sum(Payment.amount)).filter(
            Payment.tenant_id == tenant_id, Payment.status == "SUCCESS"
        ).group_by(Payment.method).all()
        return {row[0].lower() if row[0] else "unknown": row[1] or Decimal("0.0") for row in res}

    @staticmethod
    def get_pending_payments(db: Session, tenant_id: UUID) -> list:
        return db.query(Order).filter(
            Order.tenant_id == tenant_id, Order.payment_status != "PAID"
        ).all()

    @staticmethod
    def get_failed_payments(db: Session, tenant_id: UUID) -> list:
        return db.query(Payment).filter(
            Payment.tenant_id == tenant_id, Payment.status == "FAILED"
        ).all()

    @staticmethod
    def get_delivery_performance(db: Session, tenant_id: UUID) -> dict:
        res = db.query(Delivery.status, func.count(Delivery.id)).filter(
            Delivery.tenant_id == tenant_id
        ).group_by(Delivery.status).all()
        return {row[0].lower() if row[0] else "unknown": row[1] for row in res}

    @staticmethod
    def get_delivery_boy_performance(db: Session, tenant_id: UUID) -> list:
        res = db.query(
            User.id,
            User.name,
            func.count(Delivery.id).label("total_deliveries"),
            func.sum(case((Delivery.status == "DELIVERED", 1), else_=0)).label("completed"),
            func.sum(case((Delivery.type == "PICKUP", 1), else_=0)).label("pickups")
        ).join(Delivery, Delivery.delivery_boy_id == User.id).filter(
            User.tenant_id == tenant_id, User.role == "DELIVERY_BOY"
        ).group_by(User.id).all()
        return [
            {
                "id": r[0],
                "name": r[1],
                "total_tasks": r[2],
                "completed_deliveries": r[3],
                "pickup_count": r[4]
            }
            for r in res
        ]

    @staticmethod
    def get_expenses_report(db: Session, tenant_id: UUID, category: str = None) -> list:
        query = db.query(Expense).filter(Expense.tenant_id == tenant_id)
        if category:
            query = query.filter(Expense.category == category)
        return query.all()

    @staticmethod
    def get_monthly_expenses(db: Session, tenant_id: UUID) -> list:
        res = db.query(
            func.to_char(Expense.created_at, "YYYY-MM").label("month"),
            func.sum(Expense.amount).label("total_expense")
        ).filter(
            Expense.tenant_id == tenant_id
        ).group_by("month").order_by("month").all()
        return [{"month": r[0], "total_expense": r[1] or Decimal("0.0")} for r in res]

    @staticmethod
    def get_profit_report(db: Session, tenant_id: UUID) -> dict:
        revenue = db.query(func.sum(Payment.amount)).filter(
            Payment.tenant_id == tenant_id, Payment.status == "SUCCESS"
        ).scalar() or Decimal("0.0")
        
        expenses = db.query(func.sum(Expense.amount)).filter(
            Expense.tenant_id == tenant_id
        ).scalar() or Decimal("0.0")
        
        profit = revenue - expenses
        return {
            "revenue": revenue,
            "expenses": expenses,
            "profit": profit
        }

    @staticmethod
    def get_coupon_report(db: Session, tenant_id: UUID) -> dict:
        total_created = db.query(func.count(Coupon.id)).filter(
            Coupon.tenant_id == tenant_id
        ).scalar() or 0
        
        # Used coupons (Orders with discount > 0)
        orders_with_coupon = db.query(func.count(Order.id), func.sum(Order.discount)).filter(
            Order.tenant_id == tenant_id, Order.discount > 0
        ).first()
        
        used_count = orders_with_coupon[0] or 0
        discount_amount = orders_with_coupon[1] or Decimal("0.0")
        
        return {
            "coupons_created": total_created,
            "coupons_used": used_count,
            "discount_amount": discount_amount
        }

    @staticmethod
    def get_services_report(db: Session, tenant_id: UUID) -> dict:
        # Get usage and revenue per service
        services_data = db.query(
            Service.name,
            func.sum(OrderItem.quantity).label("times_used"),
            func.sum(OrderItem.quantity * OrderItem.price).label("revenue")
        ).join(OrderItem, OrderItem.service_id == Service.id).filter(
            Service.tenant_id == tenant_id
        ).group_by(Service.id).all()
        
        if not services_data:
            return {
                "services": [],
                "most_used_service": None,
                "least_used_service": None
            }
            
        services_list = [
            {
                "service_name": s[0],
                "times_used": s[1] or 0,
                "revenue": s[2] or Decimal("0.0")
            }
            for s in services_data
        ]
        
        sorted_by_usage = sorted(services_list, key=lambda x: x["times_used"])
        
        return {
            "services": services_list,
            "most_used_service": sorted_by_usage[-1]["service_name"] if sorted_by_usage else None,
            "least_used_service": sorted_by_usage[0]["service_name"] if sorted_by_usage else None
        }
