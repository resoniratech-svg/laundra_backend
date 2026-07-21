from app.models.base import Base
from app.models.company import Company
from app.models.user import User
from app.models.customer import Customer
from app.models.service import Service
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.delivery import Delivery
from app.models.expense import Expense
from app.models.coupon import Coupon
from app.models.invoice import Invoice
from app.models.notification import Notification
from app.models.audit_log import AuditLog
from app.models.subscription import Subscription
from app.models.support_ticket import SupportTicket
from app.models.company_feature import CompanyFeature
from app.models.platform_settings import PlatformSettings
from app.models.review import Review
from app.models.announcement import Announcement
from app.models.attendance import Attendance
from app.models.base import Base
from app.models.company import Company
from app.models.user import User
from app.models.customer import Customer
from app.models.service import Service
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.delivery import Delivery
from app.models.expense import Expense
from app.models.coupon import Coupon
from app.models.invoice import Invoice
from app.models.notification import Notification
from app.models.audit_log import AuditLog
from app.models.subscription import Subscription
from app.models.support_ticket import SupportTicket
from app.models.company_feature import CompanyFeature
from app.models.platform_settings import PlatformSettings
from app.models.review import Review
from app.models.announcement import Announcement
from app.models.attendance import Attendance
from app.models.leave_request import LeaveRequest
from app.models.customer_address import CustomerAddress
from app.models.subscription_plan import SubscriptionPlan
from app.models.customer_support_ticket import CustomerSupportTicket
from app.models.prepaid_package import PrepaidPackage
from app.models.customer_package import CustomerPackage
from app.models.package_usage_history import PackageUsageHistory
from app.models.wallet_pass import WalletPass

# This ensures all models are registered with SQLAlchemy Base

__all__ = [
    "Base",
    "Company",
    "User",
    "Customer",
    "Service",
    "Order",
    "OrderItem",
    "Payment",
    "Delivery",
    "Expense",
    "Coupon",
    "Invoice",
    "Notification",
    "AuditLog",
    "Subscription",
    "SupportTicket",
    "CustomerSupportTicket",
    "CompanyFeature",
    "PlatformSettings",
    "Announcement",
    "Attendance",
    "LeaveRequest",
    "CustomerAddress",
    "SubscriptionPlan",
    "PrepaidPackage",
    "CustomerPackage",
    "PackageUsageHistory",
    "WalletPass"
]
