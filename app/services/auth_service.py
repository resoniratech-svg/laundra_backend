from sqlalchemy.orm import Session
from uuid import UUID, uuid4
from fastapi import HTTPException, status
from app.core.security import get_password_hash, verify_password, create_access_token
from app.models.company import Company
from app.models.user import User
from app.models.customer import Customer
from app.core.tenant import set_current_tenant_id
from app.repositories.user_repository import UserRepository
from app.core.config import settings

user_repo = UserRepository()

class AuthService:
    @staticmethod
    def register_company(
        db: Session, 
        *, 
        company_name: str, 
        email: str, 
        phone: str, 
        password: str
    ) -> tuple[Company, User]:
        # 1. Validate duplicate user email
        existing = user_repo.find_by_email(db, email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        # 2. Create company
        company_id = uuid4()
        company = Company(
            id=company_id,
            name=company_name,
            phone=phone,
            email=email,
            password=get_password_hash(password),
            status="ACTIVE"
        )
        user_repo.create_company(db, company)

        # 3. Set current tenant context
        set_current_tenant_id(company_id)

        # 4. Create first Admin user
        admin_user = User(
            id=uuid4(),
            tenant_id=company_id,
            name=company_name + " Admin",
            phone=phone,
            email=email,
            password=get_password_hash(password),
            role="ADMIN",
            status="ACTIVE"
        )
        user_repo.create_user(db, admin_user)
        
        db.commit()
        db.refresh(company)
        db.refresh(admin_user)
        return company, admin_user

    @staticmethod
    def login(db: Session, *, email: str, password: str) -> dict:
        user = user_repo.find_by_email(db, email)
        if not user or not verify_password(password, user.password):
            return None
            
        if user.status == "PENDING_APPROVAL":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your application is under review. Please wait for approval."
            )
        elif user.status == "INACTIVE":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been deactivated."
            )
            
        if user.role not in ["SUPER_ADMIN", "CUSTOMER"]:
            from app.models.subscription import Subscription
            from datetime import date
            sub = db.query(Subscription).filter(Subscription.tenant_id == user.tenant_id).first()
            if not sub or sub.status != "ACTIVE" or (sub.end_date and sub.end_date < date.today()):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Your company's subscription has expired or is suspended. Please contact support."
                )
        
        token = create_access_token(
            subject=user.id,
            role=user.role,
            tenant_id=user.tenant_id
        )
        return {
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }

    @staticmethod
    def authenticate_customer(db: Session, *, phone: str, tenant_id: UUID) -> dict:
        customer = db.query(Customer).filter(
            Customer.phone == phone, 
            Customer.tenant_id == tenant_id
        ).first()
        
        if not customer:
            customer = Customer(
                id=uuid4(),
                tenant_id=tenant_id,
                name=f"Customer {phone[-4:]}",
                phone=phone,
                wallet_balance=0.0,
                loyalty_points=0
            )
            db.add(customer)
            db.commit()
            db.refresh(customer)
            
        token = create_access_token(
            subject=customer.id,
            role="CUSTOMER",
            tenant_id=customer.tenant_id
        )
        return {
            "access_token": token, 
            "token_type": "Bearer", 
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
