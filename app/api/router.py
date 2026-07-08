from fastapi import APIRouter
from app.api.v1 import (
    auth, companies, users, customers, services, orders, payments, deliveries, expenses, coupons, reports, dashboard,
    invoices, audit_logs, saas_admin, subscriptions, support, mobile_staff, saas_plans, saas_monitoring,
    saas_reports, saas_health, saas_support, reviews, notifications, portal
)

router = APIRouter(prefix="/api/v1")

router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(companies.router, prefix="/companies", tags=["Companies"])
router.include_router(users.router, prefix="/users", tags=["Users"])
router.include_router(customers.router, prefix="/customers", tags=["Customers"])
router.include_router(services.router, prefix="/services", tags=["Services"])
router.include_router(orders.router, prefix="/orders", tags=["Orders"])
router.include_router(payments.router, prefix="/payments", tags=["Payments"])
router.include_router(deliveries.router, prefix="/deliveries", tags=["Deliveries"])
router.include_router(expenses.router, prefix="/expenses", tags=["Expenses"])
router.include_router(coupons.router, prefix="/coupons", tags=["Coupons"])
router.include_router(reports.router, prefix="/reports", tags=["Reports"])
router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
router.include_router(invoices.router, prefix="/invoices", tags=["Invoices"])
router.include_router(audit_logs.router, prefix="/audit-logs", tags=["Audit Logs"])
router.include_router(saas_admin.router, prefix="/saas-admin", tags=["SaaS Administration"])
router.include_router(subscriptions.router, prefix="/subscriptions", tags=["Subscriptions"])
router.include_router(support.router, prefix="/support", tags=["Support Tickets"])
router.include_router(mobile_staff.router, prefix="/staff", tags=["Mobile Staff Operations"])
router.include_router(saas_plans.router, prefix="/saas/plans", tags=["SaaS Plans"])
router.include_router(saas_monitoring.router, prefix="/saas/monitoring", tags=["SaaS Monitoring"])
router.include_router(saas_reports.router, prefix="/saas/reports", tags=["SaaS Reports"])
router.include_router(saas_health.router, prefix="/saas/health", tags=["SaaS Health & Operations"])
router.include_router(saas_support.router, prefix="/saas/support", tags=["SaaS Support Tickets"])
router.include_router(reviews.router, prefix="/reviews", tags=["Reviews"])
router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
router.include_router(portal.router, prefix="/portal", tags=["Customer Portal"])

