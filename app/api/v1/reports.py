from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from app.core.database import get_db
from app.dependencies import get_current_admin
from app.models.user import User
from app.services.report_service import ReportService
from app.schemas.order import OrderOut
from app.schemas.payment import PaymentOut

router = APIRouter()

@router.get("/dashboard")
def get_dashboard(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return ReportService.get_dashboard_summary(db, current_admin.tenant_id)

@router.get("/sales/daily")
def get_daily_sales(
    target_date: Optional[date] = None,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    if not target_date:
        target_date = date.today()
    return ReportService.get_daily_sales(db, current_admin.tenant_id, target_date)

@router.get("/sales/monthly")
def get_monthly_sales(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return ReportService.get_monthly_sales(db, current_admin.tenant_id)

@router.get("/sales/yearly")
def get_yearly_sales(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return ReportService.get_yearly_sales(db, current_admin.tenant_id)

@router.get("/orders/status")
def get_orders_by_status(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return ReportService.get_orders_by_status(db, current_admin.tenant_id)

@router.get("/orders", response_model=List[OrderOut])
def get_orders_between_dates(
    start_date: date,
    end_date: date,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    orders = ReportService.get_orders_between_dates(db, current_admin.tenant_id, start_date, end_date)
    # Populate items for order schemas
    from app.models.order_item import OrderItem
    for o in orders:
        o.items = db.query(OrderItem).filter(OrderItem.order_id == o.id).all()
    return orders

@router.get("/customers/top")
def get_top_customers(
    sort_by: str = "spent", # spent | orders
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    if sort_by not in ["spent", "orders"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="sort_by parameter must be either 'spent' or 'orders'"
        )
    return ReportService.get_top_customers(db, current_admin.tenant_id, sort_by)

@router.get("/customers/growth")
def get_customer_growth(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return ReportService.get_customer_growth(db, current_admin.tenant_id)

@router.get("/customers/wallet")
def get_customer_wallet_report(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return ReportService.get_customer_wallet_report(db, current_admin.tenant_id)

@router.get("/payments/methods")
def get_revenue_by_payment_method(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return ReportService.get_revenue_by_payment_method(db, current_admin.tenant_id)

@router.get("/payments/pending", response_model=List[OrderOut])
def get_pending_payments(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    orders = ReportService.get_pending_payments(db, current_admin.tenant_id)
    from app.models.order_item import OrderItem
    for o in orders:
        o.items = db.query(OrderItem).filter(OrderItem.order_id == o.id).all()
    return orders

@router.get("/payments/failed", response_model=List[PaymentOut])
def get_failed_payments(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return ReportService.get_failed_payments(db, current_admin.tenant_id)

@router.get("/deliveries")
def get_delivery_performance(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return ReportService.get_delivery_performance(db, current_admin.tenant_id)

@router.get("/delivery-boys")
def get_delivery_boy_performance(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return ReportService.get_delivery_boy_performance(db, current_admin.tenant_id)

@router.get("/expenses")
def get_expenses_report(
    category: Optional[str] = None,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return ReportService.get_expenses_report(db, current_admin.tenant_id, category)

@router.get("/expenses/monthly")
def get_monthly_expenses(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return ReportService.get_monthly_expenses(db, current_admin.tenant_id)

@router.get("/profit")
def get_profit_report(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return ReportService.get_profit_report(db, current_admin.tenant_id)

@router.get("/coupons")
def get_coupon_report(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return ReportService.get_coupon_report(db, current_admin.tenant_id)

@router.get("/services")
def get_services_report(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return ReportService.get_services_report(db, current_admin.tenant_id)

# Export Routes
@router.get("/export/csv")
def export_csv(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    content = ReportService.export_csv(db, current_admin.tenant_id)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=performance_report.csv"}
    )

@router.get("/export/excel")
def export_excel(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    content = ReportService.export_excel(db, current_admin.tenant_id)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=performance_report.xlsx"}
    )

@router.get("/export/pdf")
def export_pdf(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    content = ReportService.export_pdf(db, current_admin.tenant_id)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=performance_report.pdf"}
    )
