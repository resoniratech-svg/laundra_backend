from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from sqlalchemy.orm import Session
from datetime import timedelta
from app.core.database import get_db



from app.api.router import router
from app.core.config import settings
from app.middleware.tenant_middleware import TenantMiddleware
from app.middleware.logging_middleware import LoggingMiddleware
from app.middleware.security_headers_middleware import SecurityHeadersMiddleware
from app.core.database import engine
from app.models import *  # noqa
from app.models.base import Base

from app.core.exceptions import (
    AppException,
    app_exception_handler,
    validation_exception_handler,
    sqlalchemy_exception_handler,
    generic_exception_handler
)

try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"[STARTUP CRITICAL] Database connection or table creation failed: {e}")

# Drop NOT NULL constraint on audit_logs.tenant_id for platform-level logs
# Isolated migration 1
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE audit_logs ALTER COLUMN tenant_id DROP NOT NULL;"))
except Exception as e:
    print(f"[STARTUP WARNING] Migration 1 failed: {e}")

# Isolated migration 2
try:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM services WHERE name LIKE '%dtype: object%';"))
        conn.execute(text("DELETE FROM services a USING services b WHERE a.id < b.id AND a.name = b.name AND a.category = b.category AND a.tenant_id = b.tenant_id;"))
except Exception as e:
    print(f"[STARTUP WARNING] Migration 2 failed: {e}")

# Isolated migration 3
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE coupons ADD COLUMN IF NOT EXISTS required_services JSON;"))
except Exception as e:
    print(f"[STARTUP WARNING] Migration 3 failed: {e}")

# Isolated migration 4
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE coupons ADD COLUMN IF NOT EXISTS name VARCHAR(100);"))
except Exception as e:
    print(f"[STARTUP WARNING] Migration 4 failed: {e}")

# Isolated migration 5
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE coupons ADD COLUMN IF NOT EXISTS start_date DATE;"))
except Exception as e:
    print(f"[STARTUP WARNING] Migration 5 failed: {e}")

# Isolated migration 6
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE coupons ADD COLUMN IF NOT EXISTS expiry_date DATE;"))
except Exception as e:
    print(f"[STARTUP WARNING] Migration 6 failed: {e}")

# Isolated migration 7 – customer extra fields
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS gender VARCHAR(20);"))
        conn.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS dob VARCHAR(50);"))
        conn.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS gst_number VARCHAR(50);"))
        conn.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS notes TEXT;"))
except Exception as e:
    print(f"[STARTUP WARNING] Migration 7 failed: {e}")

# Isolated migration 8 – customer_packages wallet fields
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE customer_packages ADD COLUMN IF NOT EXISTS package_value NUMERIC DEFAULT 0;"))
        conn.execute(text("ALTER TABLE customer_packages ADD COLUMN IF NOT EXISTS current_balance NUMERIC DEFAULT 0;"))
        conn.execute(text("ALTER TABLE customer_packages ADD COLUMN IF NOT EXISTS used_amount NUMERIC DEFAULT 0;"))
        conn.execute(text("ALTER TABLE customer_packages ADD COLUMN IF NOT EXISTS apple_wallet_url VARCHAR(500);"))
        conn.execute(text("ALTER TABLE customer_packages ADD COLUMN IF NOT EXISTS google_wallet_url VARCHAR(500);"))
        conn.execute(text("ALTER TABLE customer_packages ADD COLUMN IF NOT EXISTS pass_color VARCHAR(50);"))
        conn.execute(text("ALTER TABLE customer_packages ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'ACTIVE';"))
except Exception as e:
    print(f"[STARTUP WARNING] Migration 8 failed: {e}")

# Isolated migration 9 – prepaid_packages extra fields
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE prepaid_packages ADD COLUMN IF NOT EXISTS code VARCHAR(100);"))
except Exception as e:
    print(f"[STARTUP WARNING] Migration 9 failed: {e}")

# Isolated migration 10 – fix orphaned customers (create missing User records)
try:
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO users (id, tenant_id, name, phone, email, password, role, status, created_at, updated_at)
            SELECT c.id, c.tenant_id, c.name, c.phone, c.email, 
                   '$2b$12$Z0tT0LzE8d1L7w6w6w6w6uxX5Y3gZ3tT0LzE8d1L7w6w6w6w6w6w6', -- placeholder
                   'CUSTOMER', 'ACTIVE', NOW(), NOW()
            FROM customers c
            LEFT JOIN users u ON c.id = u.id
            WHERE u.id IS NULL
        """))
except Exception as e:
    print(f"[STARTUP WARNING] Migration 10 failed: {e}")

# Isolated migration 11 – wallet_passes table extra columns & customer_packages URL text expansion
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE wallet_passes ADD COLUMN IF NOT EXISTS class_id VARCHAR(150);"))
        conn.execute(text("ALTER TABLE wallet_passes ADD COLUMN IF NOT EXISTS pass_status VARCHAR(20) DEFAULT 'ACTIVE';"))
        conn.execute(text("ALTER TABLE customer_packages ALTER COLUMN google_wallet_url TYPE TEXT;"))
        conn.execute(text("ALTER TABLE customer_packages ALTER COLUMN apple_wallet_url TYPE TEXT;"))
except Exception as e:
    print(f"[STARTUP WARNING] Migration 11 failed: {e}")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
)

# Register Global Exception Handlers
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Middlewares
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(TenantMiddleware)

app.include_router(router)

# Initialize Google Wallet Generic Class on Application Startup
try:
    from app.wallet.class_service import create_or_get_generic_class
    wallet_res = create_or_get_generic_class()
    print(f"[GOOGLE WALLET STARTUP] {wallet_res.get('message', 'Generic Class verified')}")
except Exception as gw_e:
    print(f"[GOOGLE WALLET STARTUP WARNING] Could not verify Generic Class on startup: {gw_e}")

@app.get("/")
def home():
    return {
        "success": True,
        "message": "Laundry SaaS Backend Running Successfully 🚀"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }

@app.get("/health/database")
def health_database():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": f"error: {str(e)}"
        }

@app.get("/health/version")
def health_version():
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "debug_mode": settings.DEBUG
    }

@app.get("/track/{tracking_number}")
def public_track_order(
    tracking_number: str,
    db: Session = Depends(get_db)
):
    from app.models.order import Order
    from app.models.delivery import Delivery
    from app.models.user import User
    
    order = db.query(Order).filter(Order.order_number == tracking_number).first()
    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order tracking number not found"
        )
        
    delivery_boy_info = None
    delivery = db.query(Delivery).filter(Delivery.order_id == order.id).first()
    if delivery and delivery.delivery_boy_id:
        delivery_boy = db.query(User).filter(User.id == delivery.delivery_boy_id).first()
        if delivery_boy:
            delivery_boy_info = {
                "name": delivery_boy.name,
                "phone": delivery_boy.phone
            }
            
    estimated_delivery = order.created_at + timedelta(days=3)
    return {
        "order_number": order.order_number,
        "status": order.status,
        "payment_status": order.payment_status,
        "total_amount": order.total_amount,
        "estimated_delivery": estimated_delivery.date().isoformat(),
        "delivery_boy": delivery_boy_info
    }

