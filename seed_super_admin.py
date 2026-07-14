import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sqlalchemy import text
from app.core.database import engine, SessionLocal
from app.models.user import User
from app.core.security import get_password_hash
from uuid import uuid4

def run():
    print("Altering table...")
    with engine.begin() as conn:
        conn.execute(text('ALTER TABLE users ALTER COLUMN tenant_id DROP NOT NULL;'))
    
    print("Seeding SUPER_ADMIN...")
    db = SessionLocal()
    existing = db.query(User).filter(User.email == "superadmin@laundra.com").first()
    if not existing:
        admin = User(
            id=uuid4(),
            tenant_id=None,
            name="Platform Super Admin",
            email="superadmin@laundra.com",
            phone="0000000000",
            password=get_password_hash("admin"),
            role="SUPER_ADMIN",
            status="ACTIVE"
        )
        db.add(admin)
        db.commit()
        print("Created SUPER_ADMIN!")
    else:
        existing.role = "SUPER_ADMIN"
        existing.tenant_id = None
        db.commit()
        print("Updated existing SUPER_ADMIN!")

if __name__ == "__main__":
    run()
