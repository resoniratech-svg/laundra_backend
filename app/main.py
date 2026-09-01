from typing import Optional
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
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

# Isolated migration – expenses attachment field
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE expenses ADD COLUMN IF NOT EXISTS attachment TEXT;"))
except Exception as e:
    print(f"[STARTUP WARNING] Migration for expenses.attachment failed: {e}")

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
        conn.execute(text("ALTER TABLE wallet_passes ADD COLUMN IF NOT EXISTS pass_file_path VARCHAR(500);"))
        conn.execute(text("ALTER TABLE wallet_passes ADD COLUMN IF NOT EXISTS apple_serial_number VARCHAR(255);"))
        conn.execute(text("ALTER TABLE wallet_passes ADD COLUMN IF NOT EXISTS apple_pass_type_identifier VARCHAR(255);"))
        conn.execute(text("ALTER TABLE wallet_passes ADD COLUMN IF NOT EXISTS apple_pass_url TEXT;"))
        conn.execute(text("ALTER TABLE wallet_passes ADD COLUMN IF NOT EXISTS qr_url TEXT;"))
        conn.execute(text("ALTER TABLE wallet_passes ADD COLUMN IF NOT EXISTS wallet_status VARCHAR(50) DEFAULT 'ACTIVE';"))
        conn.execute(text("ALTER TABLE wallet_passes ADD COLUMN IF NOT EXISTS original_amount NUMERIC(10, 2);"))
        conn.execute(text("ALTER TABLE wallet_passes ADD COLUMN IF NOT EXISTS remaining_balance NUMERIC(10, 2);"))
        conn.execute(text("ALTER TABLE wallet_passes ADD COLUMN IF NOT EXISTS expiry_date TIMESTAMP WITH TIME ZONE;"))
        conn.execute(text("ALTER TABLE wallet_passes ADD COLUMN IF NOT EXISTS wallet_created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();"))
        conn.execute(text("ALTER TABLE wallet_passes ADD COLUMN IF NOT EXISTS wallet_updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();"))
        conn.execute(text("ALTER TABLE wallet_passes ADD COLUMN IF NOT EXISTS class_id VARCHAR(150);"))
        conn.execute(text("ALTER TABLE wallet_passes ADD COLUMN IF NOT EXISTS pass_status VARCHAR(20) DEFAULT 'ACTIVE';"))
        conn.execute(text("ALTER TABLE wallet_passes ADD COLUMN IF NOT EXISTS google_class_id VARCHAR(150);"))
        conn.execute(text("ALTER TABLE wallet_passes ADD COLUMN IF NOT EXISTS google_object_id VARCHAR(150);"))
        conn.execute(text("ALTER TABLE wallet_passes ADD COLUMN IF NOT EXISTS google_wallet_url TEXT;"))
        conn.execute(text("ALTER TABLE wallet_passes ADD COLUMN IF NOT EXISTS order_id UUID;"))
        conn.execute(text("ALTER TABLE wallet_passes ADD COLUMN IF NOT EXISTS pass_type_identifier VARCHAR(255);"))
        conn.execute(text("ALTER TABLE wallet_passes ADD COLUMN IF NOT EXISTS serial_number VARCHAR(255);"))
        conn.execute(text("ALTER TABLE wallet_passes ADD COLUMN IF NOT EXISTS authentication_token VARCHAR(255);"))
        conn.execute(text("ALTER TABLE wallet_passes ADD COLUMN IF NOT EXISTS qr_token VARCHAR(500);"))
        conn.execute(text("ALTER TABLE wallet_passes ADD COLUMN IF NOT EXISTS wallet_sync_status VARCHAR(20) DEFAULT 'SYNCED';"))
        conn.execute(text("ALTER TABLE wallet_passes ADD COLUMN IF NOT EXISTS wallet_sync_error TEXT;"))
        conn.execute(text("ALTER TABLE wallet_passes ADD COLUMN IF NOT EXISTS wallet_sync_attempts INTEGER DEFAULT 0;"))
        conn.execute(text("ALTER TABLE customer_packages ALTER COLUMN google_wallet_url TYPE TEXT;"))
        conn.execute(text("ALTER TABLE customer_packages ALTER COLUMN apple_wallet_url TYPE TEXT;"))
except Exception as e:
    print(f"[STARTUP WARNING] Migration 11 failed: {e}")

# Isolated migration 12 – populate null/empty values and drop strict NOT NULL constraints on legacy columns
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE wallet_passes ALTER COLUMN wallet_object_id DROP NOT NULL;"))
        conn.execute(text("UPDATE wallet_passes SET wallet_object_id = 'OBJ-' || UPPER(SUBSTRING(REPLACE(customer_package_id::text, '-', '') FROM 1 FOR 12)) WHERE (wallet_object_id IS NULL OR wallet_object_id = '') AND customer_package_id IS NOT NULL;"))
        conn.execute(text("UPDATE wallet_passes SET wallet_object_id = 'OBJ-' || UPPER(SUBSTRING(REPLACE(id::text, '-', '') FROM 1 FOR 12)) WHERE (wallet_object_id IS NULL OR wallet_object_id = '');"))
        
        conn.execute(text("UPDATE wallet_passes SET google_object_id = 'GOBJ-' || UPPER(SUBSTRING(REPLACE(customer_package_id::text, '-', '') FROM 1 FOR 12)) WHERE (google_object_id IS NULL OR google_object_id = '') AND customer_package_id IS NOT NULL;"))
        conn.execute(text("UPDATE wallet_passes SET google_object_id = 'GOBJ-' || UPPER(SUBSTRING(REPLACE(id::text, '-', '') FROM 1 FOR 12)) WHERE (google_object_id IS NULL OR google_object_id = '');"))
        
        conn.execute(text("UPDATE wallet_passes SET class_id = 'CLASS-LAUNDRA-PASS' WHERE (class_id IS NULL OR class_id = '');"))
        conn.execute(text("UPDATE wallet_passes SET google_class_id = 'GCLASS-LAUNDRA-PASS' WHERE (google_class_id IS NULL OR google_class_id = '');"))
        
        conn.execute(text("UPDATE wallet_passes SET wallet_url = COALESCE(NULLIF(apple_pass_url, ''), NULLIF(qr_url, ''), '/api/v1/wallet/apple/pass/' || id::text) WHERE (wallet_url IS NULL OR wallet_url = '');"))
except Exception as e:
    print(f"[STARTUP WARNING] Migration 12 failed: {e}")

# Isolated migration 13 – set DEFAULT NOW() on wallet_passes.created_at & updated_at
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE wallet_passes ALTER COLUMN created_at SET DEFAULT NOW();"))
        conn.execute(text("ALTER TABLE wallet_passes ALTER COLUMN updated_at SET DEFAULT NOW();"))
        conn.execute(text("UPDATE wallet_passes SET created_at = NOW() WHERE created_at IS NULL;"))
        conn.execute(text("UPDATE wallet_passes SET updated_at = NOW() WHERE updated_at IS NULL;"))
except Exception as e:
    print(f"[STARTUP WARNING] Migration 13 failed: {e}")

# Isolated migration 14 – OrderItem and Order item-level partial pickup & delivery columns
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE order_items ADD COLUMN IF NOT EXISTS ordered_quantity INTEGER;"))
        conn.execute(text("ALTER TABLE order_items ADD COLUMN IF NOT EXISTS picked_up_quantity INTEGER DEFAULT 0;"))
        conn.execute(text("ALTER TABLE order_items ADD COLUMN IF NOT EXISTS pickup_pending_quantity INTEGER;"))
        conn.execute(text("ALTER TABLE order_items ADD COLUMN IF NOT EXISTS delivered_quantity INTEGER DEFAULT 0;"))
        conn.execute(text("ALTER TABLE order_items ADD COLUMN IF NOT EXISTS delivery_pending_quantity INTEGER DEFAULT 0;"))
        conn.execute(text("ALTER TABLE order_items ADD COLUMN IF NOT EXISTS item_status VARCHAR(30) DEFAULT 'CREATED';"))
        conn.execute(text("UPDATE order_items SET ordered_quantity = quantity WHERE ordered_quantity IS NULL;"))
        conn.execute(text("UPDATE order_items SET pickup_pending_quantity = ordered_quantity - COALESCE(picked_up_quantity, 0) WHERE pickup_pending_quantity IS NULL;"))
        conn.execute(text("UPDATE order_items SET delivery_pending_quantity = COALESCE(picked_up_quantity, 0) - COALESCE(delivered_quantity, 0) WHERE delivery_pending_quantity IS NULL;"))
        conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS pickup_history TEXT;"))
        conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_history TEXT;"))
except Exception as e:
    print(f"[STARTUP WARNING] Migration 14 failed: {e}")

# Isolated migration 15 – customer_packages legacy columns mapping
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE customer_packages ADD COLUMN IF NOT EXISTS wash_total INTEGER DEFAULT 0;"))
        conn.execute(text("ALTER TABLE customer_packages ADD COLUMN IF NOT EXISTS wash_left INTEGER DEFAULT 0;"))
        conn.execute(text("ALTER TABLE customer_packages ADD COLUMN IF NOT EXISTS iron_total INTEGER DEFAULT 0;"))
        conn.execute(text("ALTER TABLE customer_packages ADD COLUMN IF NOT EXISTS iron_left INTEGER DEFAULT 0;"))
        conn.execute(text("ALTER TABLE customer_packages ADD COLUMN IF NOT EXISTS dry_total INTEGER DEFAULT 0;"))
        conn.execute(text("ALTER TABLE customer_packages ADD COLUMN IF NOT EXISTS dry_left INTEGER DEFAULT 0;"))
        conn.execute(text("ALTER TABLE customer_packages ADD COLUMN IF NOT EXISTS steam_total INTEGER DEFAULT 0;"))
        conn.execute(text("ALTER TABLE customer_packages ADD COLUMN IF NOT EXISTS steam_left INTEGER DEFAULT 0;"))
except Exception as e:
    print(f"[STARTUP WARNING] Migration 15 failed: {e}")

# Isolated migration 16 – package_usage_history remarks column + order_id nullable
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE package_usage_history ADD COLUMN IF NOT EXISTS remarks TEXT;"))
        conn.execute(text("ALTER TABLE package_usage_history ALTER COLUMN order_id DROP NOT NULL;"))
except Exception as e:
    print(f"[STARTUP WARNING] Migration 16 failed: {e}")

# Isolated migration 17 – customer_packages service_items JSONB column
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE customer_packages ADD COLUMN IF NOT EXISTS service_items JSONB;"))
except Exception as e:
    print(f"[STARTUP WARNING] Migration 17 failed: {e}")

# Isolated migration 18 – fix wallet_passes foreign key constraint to ON DELETE SET NULL & DROP NOT NULL
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE wallet_passes ALTER COLUMN customer_package_id DROP NOT NULL;"))
        conn.execute(text("ALTER TABLE wallet_passes DROP CONSTRAINT IF EXISTS wallet_passes_customer_package_id_fkey;"))
        conn.execute(text("ALTER TABLE wallet_passes ADD CONSTRAINT wallet_passes_customer_package_id_fkey FOREIGN KEY (customer_package_id) REFERENCES customer_packages(id) ON DELETE SET NULL;"))
except Exception as e:
    print(f"[STARTUP WARNING] Migration 18 failed: {e}")

# Isolated migration 19 – Commission columns for orders and deliveries tables
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS pickup_commission NUMERIC(10, 2) DEFAULT 0.0;"))
        conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_commission NUMERIC(10, 2) DEFAULT 0.0;"))
        conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS pickup_staff_id UUID;"))
        conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_staff_id UUID;"))
        conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS pickup_commission_paid BOOLEAN DEFAULT FALSE;"))
        conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_commission_paid BOOLEAN DEFAULT FALSE;"))

        conn.execute(text("ALTER TABLE deliveries ADD COLUMN IF NOT EXISTS pickup_commission NUMERIC(10, 2) DEFAULT 0.0;"))
        conn.execute(text("ALTER TABLE deliveries ADD COLUMN IF NOT EXISTS delivery_commission NUMERIC(10, 2) DEFAULT 0.0;"))
        conn.execute(text("ALTER TABLE deliveries ADD COLUMN IF NOT EXISTS pickup_commission_paid BOOLEAN DEFAULT FALSE;"))
        conn.execute(text("ALTER TABLE deliveries ADD COLUMN IF NOT EXISTS delivery_commission_paid BOOLEAN DEFAULT FALSE;"))
except Exception as e:
    print(f"[STARTUP WARNING] Migration 19 failed: {e}")

# Isolated migration 20 – payment_method columns for commissions in deliveries and orders
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE deliveries ADD COLUMN IF NOT EXISTS pickup_payment_method VARCHAR(50);"))
        conn.execute(text("ALTER TABLE deliveries ADD COLUMN IF NOT EXISTS delivery_payment_method VARCHAR(50);"))
        conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_method VARCHAR(50);"))
        conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS pickup_payment_method VARCHAR(50);"))
        conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_payment_method VARCHAR(50);"))
except Exception as e:
    print(f"[STARTUP WARNING] Migration 20 failed: {e}")

# Isolated migration 21 – driver_settlements table and handover settled tracking
try:
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS driver_settlements (
                id UUID PRIMARY KEY,
                tenant_id UUID NOT NULL,
                settlement_number VARCHAR(100),
                driver_id UUID,
                driver_name VARCHAR(255),
                settled_by VARCHAR(255),
                settled_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                cash_amount NUMERIC(10, 2) DEFAULT 0.0,
                card_amount NUMERIC(10, 2) DEFAULT 0.0,
                cheque_amount NUMERIC(10, 2) DEFAULT 0.0,
                total_amount NUMERIC(10, 2) DEFAULT 0.0,
                order_count INTEGER DEFAULT 0,
                orders JSONB,
                notes TEXT,
                status VARCHAR(50) DEFAULT 'SETTLED',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """))
        conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS handover_settled BOOLEAN DEFAULT FALSE;"))
        conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS handover_settled_at TIMESTAMP WITH TIME ZONE;"))
        conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS handover_settled_by VARCHAR(255);"))
        conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS handover_settlement_id VARCHAR(100);"))
except Exception as e:
    print(f"[STARTUP WARNING] Migration 21 failed: {e}")

try:
    import alembic.config
    import alembic.command
    alembic_cfg = alembic.config.Config("alembic.ini")
    alembic.command.upgrade(alembic_cfg, "head")
    print("[STARTUP] Alembic migrations applied successfully.")
except Exception as e:
    print(f"[STARTUP WARNING] Alembic migration failed: {e}")


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

# Custom Middlewares
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(TenantMiddleware)

from app.core.logging import logger, sanitize_sensitive_data

try:
    from seed_super_admin import run as seed_super_admin_run
    seed_super_admin_run()
    print("[STARTUP] Superadmin seed check completed.")
except Exception as e:
    print(f"[STARTUP WARNING] Superadmin seed failed: {e}")

# Cache Apple Wallet certificates in memory at startup
try:
    from app.services.apple_wallet.certificate_service import CertificateService
    CertificateService.load_and_cache_certificates()
    print("[STARTUP] Apple Wallet certificates cached in memory.")
except Exception as e:
    print(f"[STARTUP WARNING] Apple Wallet certificate caching failed: {e}")

# CORS configuration MUST BE LAST to wrap all other middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", 
        "https://localhost:5173",
        "http://127.0.0.1:5173",
        "https://laundry-project-laundry-frontend.cocjl5.easypanel.host",
        "https://laundra-test-laundry-frontend-test.cocjl5.easypanel.host",
        settings.FRONTEND_BASE_URL
    ],
    allow_origin_regex=r"https://.*\.easypanel\.host|http://localhost:.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/verify/pass/{serial_number}")
def public_verify_pass(
    serial_number: str,
    token: Optional[str] = None,
    format: Optional[str] = None,
    db: Session = Depends(get_db)
):
    from app.models.wallet_pass import WalletPass
    from app.models.customer_package import CustomerPackage
    from app.models.user import User
    from app.services.wallet_service import WalletService
    from fastapi.responses import HTMLResponse, FileResponse
    from pathlib import Path
    import uuid

    # Look up by serial number, authentication token, or ID
    pass_rec = db.query(WalletPass).filter(
        (WalletPass.serial_number == serial_number) |
        (WalletPass.apple_serial_number == serial_number) |
        (WalletPass.authentication_token == token)
    ).first()

    cp = None
    if pass_rec and pass_rec.customer_package_id:
        cp = db.query(CustomerPackage).filter(CustomerPackage.id == pass_rec.customer_package_id).first()

    if not cp:
        # Fallback search by secure token or package id
        try:
            val_uuid = uuid.UUID(serial_number)
            cp = db.query(CustomerPackage).filter(CustomerPackage.id == val_uuid).first()
        except Exception:
            pass
        if not cp:
            cp = db.query(CustomerPackage).filter(CustomerPackage.secure_token == serial_number).first()

    if not cp:
        raise HTTPException(status_code=404, detail="Pass or Customer Package not found")

    if not pass_rec:
        pass_rec = WalletService.resolve_wallet_pass(
            db=db,
            serial_number=serial_number,
            customer_id=cp.customer_id,
            customer_package_id=cp.id
        )

    customer = db.query(User).filter(User.id == cp.customer_id).first()
    
    # Auto-refresh pass file on disk
    try:
        WalletService.update_wallet_pass_on_usage(db, cp, customer)
    except Exception as e:
        pass

    # If requested format is pkpass or download parameter is true
    if format == "pkpass" or token == "pkpass":
        if pass_rec and pass_rec.pass_file_path and Path(pass_rec.pass_file_path).exists():
            return FileResponse(
                path=Path(pass_rec.pass_file_path),
                media_type="application/vnd.apple.pkpass",
                filename=f"package_{cp.secure_token[:8]}.pkpass"
            )

    cust_name = customer.name if customer else "Member"
    pkg_name = cp.package.name if hasattr(cp, 'package') and cp.package else "Prepaid Package"
    bal_val = f"QR {float(cp.current_balance or 0.0):.2f}"
    exp_date = cp.expiry_date.strftime("%Y-%m-%d") if (cp.expiry_date and hasattr(cp.expiry_date, 'strftime')) else str(cp.expiry_date or "N/A")
    status_str = cp.status or "ACTIVE"

    # Services breakdown
    service_items = cp.service_items or []
    services_html = ""
    if service_items:
        for si in service_items:
            s_name = si.get("service", "Service")
            s_left = si.get("left", 0)
            s_total = si.get("total", 0)
            percent = int((s_left / s_total * 100)) if s_total > 0 else 0
            bar_color = "#16a34a" if percent > 50 else ("#d97706" if percent > 20 else "#dc2626")
            services_html += f"""
            <div style="margin-bottom: 14px;">
              <div style="display:flex; justify-content:space-between; font-size:14px; font-weight:700; color:#334155; margin-bottom:6px;">
                <span>{s_name}</span>
                <span>{s_left} / {s_total} Pcs</span>
              </div>
              <div style="height:10px; background:#e2e8f0; border-radius:5px; overflow:hidden;">
                <div style="width:{percent}%; height:100%; background:{bar_color}; border-radius:5px;"></div>
              </div>
            </div>
            """
    else:
        services_html = "<div style='color:#64748b; font-size:14px;'>Package services active</div>"

    download_link = f"/api/v1/wallet/apple/pass/{cp.secure_token}"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>{cust_name} - Laundry Pass</title>
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8fafc; margin: 0; padding: 20px; display: flex; justify-content: center; align-items: center; min-height: 90vh; }}
        .card {{ background: white; max-width: 420px; width: 100%; border-radius: 20px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.05); overflow: hidden; border: 1px solid #e2e8f0; }}
        .header {{ background: linear-gradient(135deg, #eab308, #ca8a04); padding: 24px; color: white; text-align: center; }}
        .header.in_use {{ background: linear-gradient(135deg, #64748b, #475569); }}
        .header.completed {{ background: linear-gradient(135deg, #94a3b8, #64748b); }}
        .badge {{ display: inline-block; padding: 4px 12px; background: rgba(255,255,255,0.25); border-radius: 20px; font-size: 12px; font-weight: 800; letter-spacing: 1px; text-transform: uppercase; margin-top: 6px; }}
        .content {{ padding: 24px; }}
        .btn {{ display: block; width: 100%; padding: 14px; background: #000; color: white; text-align: center; border-radius: 12px; text-decoration: none; font-weight: 700; font-size: 16px; margin-top: 20px; box-sizing: border-box; transition: background 0.2s; }}
        .btn:hover {{ background: #1e293b; }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="header {'in_use' if status_str == 'IN_USE' else ('completed' if status_str == 'COMPLETED' else '')}">
          <div style="font-size: 13px; opacity: 0.9; text-transform: uppercase; letter-spacing: 1px; font-weight: 700;">Dry Cleaners Official Pass</div>
          <h2 style="margin: 6px 0 0 0; font-size: 24px; font-weight: 800;">{pkg_name}</h2>
          <div class="badge">{status_str}</div>
        </div>
        <div class="content">
          <div style="margin-bottom: 20px; border-bottom: 1px solid #f1f5f9; padding-bottom: 16px;">
            <div style="font-size: 12px; color: #64748b; font-weight: 700; text-transform: uppercase;">Customer Name</div>
            <div style="font-size: 20px; font-weight: 800; color: #0f172a; margin-top: 2px;">{cust_name}</div>
          </div>
          
          <div style="margin-bottom: 20px;">
            <div style="font-size: 12px; color: #64748b; font-weight: 700; text-transform: uppercase; margin-bottom: 12px;">Included Service Balances</div>
            {services_html}
          </div>

          <div style="display: flex; justify-content: space-between; font-size: 13px; color: #64748b; padding: 12px; background: #f8fafc; border-radius: 10px;">
            <div>Wallet Balance: <strong style="color: #0f172a;">{bal_val}</strong></div>
            <div>Expires: <strong style="color: #0f172a;">{exp_date}</strong></div>
          </div>

          <a href="{download_link}" class="btn">📲 Add to Apple Wallet / Download Pass</a>
        </div>
      </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

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


@app.get("/privacy", response_class=HTMLResponse)
@app.get("/data-deletion", response_class=HTMLResponse)
def privacy_policy():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Privacy Policy & Account Data Deletion - Laundra Delivery</title>
      <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #1e293b; background-color: #f8fafc; margin: 0; padding: 40px 20px; }
        .container { max-width: 800px; margin: 0 auto; background: #ffffff; padding: 40px; border-radius: 16px; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); }
        h1 { color: #2563eb; margin-top: 0; font-size: 28px; }
        h2 { color: #0f172a; margin-top: 28px; border-bottom: 2px solid #f1f5f9; padding-bottom: 8px; font-size: 20px; }
        p, li { color: #475569; font-size: 15px; }
        ul { padding-left: 20px; }
        .contact-card { background: #eff6ff; border-left: 4px solid #2563eb; padding: 16px 20px; margin-top: 20px; border-radius: 8px; }
      </style>
    </head>
    <body>
      <div class="container">
        <h1>Privacy Policy & Data Deletion Policy</h1>
        <p><strong>Effective Date:</strong> August 10, 2026</p>
        <p>This Privacy Policy explains how <strong>Laundra Delivery</strong> ("we", "us", or "our") collects, uses, and protects your information when you use our mobile application and delivery operations platform.</p>
        
        <h2>1. Information We Collect</h2>
        <p>To provide reliable pickup and delivery services, we may collect:</p>
        <ul>
          <li><strong>Personal Details:</strong> Name, phone number, email address.</li>
          <li><strong>Delivery Data:</strong> Order details, pickup/drop-off addresses, delivery completion logs.</li>
          <li><strong>Device Information:</strong> App usage metrics, login authentication tokens.</li>
        </ul>

        <h2>2. How We Use Your Information</h2>
        <ul>
          <li>To assign, manage, and complete laundry pickup and delivery tasks.</li>
          <li>To process delivery agent earnings, commissions, and shift management.</li>
          <li>To provide customer support and operational announcements.</li>
        </ul>

        <h2>3. Data Sharing & Security</h2>
        <p>We strictly do NOT sell or share your personal data with third-party advertisers. All data is encrypted in transit using SSL/TLS encryption and stored on secure cloud database servers.</p>

        <h2>4. User Rights & Account Data Deletion Request</h2>
        <p>You have the right to request access to or deletion of your account and associated personal data at any time.</p>
        <p><strong>To request account data deletion:</strong></p>
        <ul>
          <li>Email our support team at <strong>kanikarapubhanup@gmail.com</strong> with the subject line <em>"Account Data Deletion Request"</em>.</li>
          <li>Provide your registered phone number or email address.</li>
          <li>Upon verification, your account and personal data will be permanently purged from our active systems within 30 days.</li>
        </ul>

        <h2>5. Contact Us</h2>
        <div class="contact-card">
          <p style="margin:0; font-weight:bold; color:#1e40af;">Laundra Delivery Operations Support</p>
          <p style="margin:4px 0 0 0;">Email: <a href="mailto:kanikarapubhanup@gmail.com">kanikarapubhanup@gmail.com</a></p>
        </div>
      </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


