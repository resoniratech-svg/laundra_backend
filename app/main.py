from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from sqlalchemy.orm import Session
from datetime import timedelta
from app.core.database import get_db

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI()
# Allow requests from the Vite frontend
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all HTTP methods (GET, POST, etc.)
    allow_headers=["*"], # Allows all headers
)

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

Base.metadata.create_all(bind=engine)

# Drop NOT NULL constraint on audit_logs.tenant_id for platform-level logs
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE audit_logs ALTER COLUMN tenant_id DROP NOT NULL;"))
        conn.execute(text("DELETE FROM services WHERE name LIKE '%dtype: object%';"))
        conn.execute(text("DELETE FROM services a USING services b WHERE a.id < b.id AND a.name = b.name AND a.category = b.category AND a.tenant_id = b.tenant_id;"))
except Exception as e:
    print(f"[STARTUP WARNING] Failed database startup migrations or cleanups: {e}")

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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Middlewares
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(TenantMiddleware)

app.include_router(router)

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

