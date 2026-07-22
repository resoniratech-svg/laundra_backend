import sys
from sqlalchemy import text
from app.core.database import SessionLocal, engine

def migrate_more():
    print("Fixing wallet_passes table to match the model exactly...")
    db = SessionLocal()
    try:
        # Check existing columns
        existing_cols_result = db.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name='wallet_passes'"
        ))
        existing_cols = {row[0] for row in existing_cols_result}

        # Rename company_id to tenant_id if it exists
        if 'company_id' in existing_cols and 'tenant_id' not in existing_cols:
            print("Renaming company_id to tenant_id")
            db.execute(text("ALTER TABLE wallet_passes RENAME COLUMN company_id TO tenant_id"))

        # Add missing columns
        columns = {
            "order_id": "UUID",
            "pass_type_identifier": "VARCHAR(255)",
            "serial_number": "VARCHAR(255)",
            "authentication_token": "VARCHAR(255)",
            "qr_token": "VARCHAR(500)",
            "pass_file_path": "VARCHAR(500)"
        }

        for col, col_type in columns.items():
            if col not in existing_cols:
                print(f"Adding column {col} ({col_type})")
                db.execute(text(f"ALTER TABLE wallet_passes ADD COLUMN {col} {col_type}"))

        db.commit()
        print("Migration 2 completed.")
    except Exception as e:
        print(f"Error during migration: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    migrate_more()
