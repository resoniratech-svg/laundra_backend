from app.core.database import engine
from app.models.base import BaseModel
from sqlalchemy import text
from app.models import * # Import all to ensure they are registered in Base

def migrate():
    print("Creating new tables...")
    BaseModel.metadata.create_all(bind=engine)
    
    with engine.begin() as conn:
        print("Altering companies table...")
        conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS gst_number VARCHAR(50);"))
        conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS business_type VARCHAR(100);"))
        
        print("Altering subscriptions table...")
        # drop old
        conn.execute(text("ALTER TABLE subscriptions DROP COLUMN IF EXISTS max_users;"))
        conn.execute(text("ALTER TABLE subscriptions DROP COLUMN IF EXISTS max_orders;"))
        
        # add new
        conn.execute(text("ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS max_admins INTEGER DEFAULT 1;"))
        conn.execute(text("ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS max_cashiers INTEGER DEFAULT 0;"))
        conn.execute(text("ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS max_delivery_staff INTEGER DEFAULT 0;"))
        conn.execute(text("ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS max_customers INTEGER DEFAULT 100;"))
        conn.execute(text("ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS max_orders_per_month INTEGER DEFAULT 100;"))
        conn.execute(text("ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS max_storage_mb INTEGER DEFAULT 1024;"))
        conn.execute(text("ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS max_api_requests INTEGER DEFAULT 1000;"))
        
        print("Migration complete!")

if __name__ == "__main__":
    migrate()
