import sys
from sqlalchemy import text
from app.core.database import SessionLocal, engine

def fix_created_at():
    print("Setting defaults for created_at and updated_at...")
    db = SessionLocal()
    try:
        db.execute(text("ALTER TABLE wallet_passes ALTER COLUMN created_at SET DEFAULT NOW()"))
        db.execute(text("ALTER TABLE wallet_passes ALTER COLUMN updated_at SET DEFAULT NOW()"))
        db.commit()
        print("Defaults set.")
    except Exception as e:
        print(f"Error during migration: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_created_at()
