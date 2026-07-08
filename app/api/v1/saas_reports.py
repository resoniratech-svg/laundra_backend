from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter()

def get_current_super_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only SaaS super administrators can access this resource"
        )
    return current_user

@router.get("/revenue")
def get_platform_revenue(
    days: int = 30,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    # Mocking revenue for now based on active subscriptions
    from app.models.subscription import Subscription
    
    active_subs = db.query(Subscription.plan_name, func.count(Subscription.id)).filter(Subscription.status == "ACTIVE").group_by(Subscription.plan_name).all()
    mrr = 0.0
    for plan, count in active_subs:
        if plan == "STARTER": mrr += count * 49.0
        elif plan == "PROFESSIONAL": mrr += count * 99.0
        elif plan == "ENTERPRISE": mrr += count * 299.0
        
    return {
        "period_days": days,
        "monthly_recurring_revenue": mrr,
        "annual_run_rate": mrr * 12
    }

@router.get("/growth")
def get_platform_growth(
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.models.company import Company
    
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    new_companies = db.query(func.count(Company.id)).filter(Company.created_at >= thirty_days_ago).scalar() or 0
    total_companies = db.query(func.count(Company.id)).scalar() or 0
    
    growth_rate = 0
    if total_companies > 0:
        growth_rate = (new_companies / total_companies) * 100
        
    return {
        "new_companies_last_30_days": new_companies,
        "total_companies": total_companies,
        "monthly_growth_rate_percent": round(growth_rate, 2)
    }

@router.get("/feature-usage")
def get_feature_usage(
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.models.company_feature import CompanyFeature
    
    features = db.query(CompanyFeature.feature_key, func.count(CompanyFeature.id)).filter(CompanyFeature.is_enabled == True).group_by(CompanyFeature.feature_key).all()
    
    return {
        "active_features": [{"feature": f[0], "companies_using": f[1]} for f in features]
    }
