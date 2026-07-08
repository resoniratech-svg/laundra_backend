from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.config import settings
from app.core.database import get_db
from app.core.tenant import set_current_tenant_id
from app.models.user import User
from app.models.customer import Customer
from app.core.security import decode_access_token
from app.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
user_repo = UserRepository()

def get_token_data(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id_raw: str = payload.get("sub")
        role: str = payload.get("role")
        tenant_id: str = payload.get("tenant_id")
        if user_id_raw is None or role is None or tenant_id is None:
            raise credentials_exception
            
        qr_secret = None
        if ":" in user_id_raw:
            user_id, qr_secret = user_id_raw.split(":", 1)
        else:
            user_id = user_id_raw
            
        return {"user_id": user_id, "role": role, "tenant_id": tenant_id, "qr_secret": qr_secret}
    except JWTError:
        raise credentials_exception

def get_current_user(
    token_data: dict = Depends(get_token_data),
    db: Session = Depends(get_db)
) -> User:
    tenant_id = UUID(token_data["tenant_id"])
    set_current_tenant_id(tenant_id)
    
    user = user_repo.get_user_by_id(db, UUID(token_data["user_id"]))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user does not have enough privileges"
        )
    return current_user

def get_current_super_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user does not have enough privileges. Must be Super Admin."
        )
    return current_user

def get_current_admin_or_cashier(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ["ADMIN", "CASHIER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user does not have enough privileges. Must be Admin or Cashier."
        )
    return current_user

def get_current_delivery_boy(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "DELIVERY_BOY":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user is not a delivery boy"
        )
    return current_user

def get_current_customer(
    token_data: dict = Depends(get_token_data),
    db: Session = Depends(get_db)
) -> Customer:
    tenant_id = UUID(token_data["tenant_id"])
    set_current_tenant_id(tenant_id)
    
    if token_data["role"] != "CUSTOMER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access token is not for a customer"
        )
        
    customer = db.query(Customer).filter(Customer.id == UUID(token_data["user_id"])).first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
        
    if token_data.get("qr_secret"):
        if not customer.qr_secret or customer.qr_secret != token_data["qr_secret"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="QR token has been revoked or is invalid"
            )
            
    return customer

def require_feature(feature_key: str):
    def dependency(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        from app.models.company_feature import CompanyFeature
        feat = db.query(CompanyFeature).filter(
            CompanyFeature.tenant_id == current_user.tenant_id,
            CompanyFeature.feature_key == feature_key.upper(),
            CompanyFeature.is_enabled == True
        ).first()
        if not feat:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"The feature '{feature_key}' is not enabled for your company subscription plan."
            )
        return True
    return dependency

def check_subscription_active(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.models.subscription import Subscription
    from datetime import date
    
    sub = db.query(Subscription).filter(
        Subscription.tenant_id == current_user.tenant_id
    ).first()
    
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="No active subscription found. Please contact support."
        )
        
    if sub.status in ["EXPIRED", "SUSPENDED"]:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Your subscription plan ({sub.plan_name}) is {sub.status.lower()}. Please upgrade to proceed."
        )
        
    if sub.end_date < date.today():
        sub.status = "EXPIRED"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Your subscription plan has expired. Please upgrade or renew your subscription."
        )
        
    return True


