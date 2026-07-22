import sys
from sqlalchemy import text
from app.core.database import SessionLocal, engine

def fix_constraints():
    print("Dropping NOT NULL constraints for wallet_passes...")
    db = SessionLocal()
    try:
        columns_to_make_nullable = [
            "wallet_object_id",
            "wallet_url",
            "class_id",
            "pass_type_identifier",
            "serial_number",
            "authentication_token",
            "qr_token",
            "pass_file_path"
        ]

        for col in columns_to_make_nullable:
            try:
                db.execute(text(f"ALTER TABLE wallet_passes ALTER COLUMN {col} DROP NOT NULL"))
                print(f"Dropped NOT NULL for {col}")
            except Exception as e:
                print(f"Skipped {col}: {e}")
                
        db.commit()
        print("Constraints fixed.")
    except Exception as e:
        print(f"Error during migration: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_constraints()
