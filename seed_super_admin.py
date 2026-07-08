from app.core.database import SessionLocal
from app.models.user import User
from app.models.company import Company
from app.core.security import get_password_hash
from uuid import uuid4

def seed_super_admin():
    db = SessionLocal()
    
    # Check if super admin exists
    super_admin = db.query(User).filter(User.role == "SUPER_ADMIN").first()
    if not super_admin:
        # Create a dummy company for the super admin (since tenant_id is required in User model)
        # Or better, just get an existing company
        company = db.query(Company).first()
        if not company:
            company = Company(
                id=uuid4(),
                name="System Company",
                email="system@laundry.com",
                phone="0000000000",
                password=get_password_hash("dummy123"),
                status="ACTIVE"
            )
            db.add(company)
            db.commit()
            db.refresh(company)
            
        super_admin = User(
            id=uuid4(),
            tenant_id=company.id,
            name="Super Admin",
            email="superadmin@laundry.com",
            phone="1234567890",
            password=get_password_hash("admin123"),
            role="SUPER_ADMIN",
            status="ACTIVE"
        )
        db.add(super_admin)
        db.commit()
        print("Super Admin created: superadmin@laundry.com / admin123")
    else:
        # Reset password to ensure we know it
        super_admin.password = get_password_hash("admin123")
        super_admin.email = "superadmin@laundry.com"
        db.commit()
        print("Super Admin updated: superadmin@laundry.com / admin123")

if __name__ == "__main__":
    seed_super_admin()
