import sys
import os
from sqlalchemy import text
from app.core.database import SessionLocal, engine

def migrate():
    print("Migrating wallet_passes table...")
    db = SessionLocal()
    try:
        # Check if table exists
        result = db.execute(text("SELECT to_regclass('wallet_passes')")).scalar()
        if not result:
            print("Table wallet_passes does not exist yet. Will be created by create_all.")
            return

        # List of columns to add with their types
        columns = {
            "customer_package_id": "UUID",
            "apple_serial_number": "VARCHAR(255)",
            "apple_pass_type_identifier": "VARCHAR(255)",
            "apple_pass_url": "TEXT",
            "google_class_id": "VARCHAR(255)",
            "google_object_id": "VARCHAR(255)",
            "google_wallet_url": "TEXT",
            "qr_url": "TEXT",
            "wallet_status": "VARCHAR(50) DEFAULT 'ACTIVE'",
            "original_amount": "NUMERIC(10, 2)",
            "remaining_balance": "NUMERIC(10, 2)",
            "expiry_date": "TIMESTAMP WITH TIME ZONE",
            "wallet_created_at": "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
            "wallet_updated_at": "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
        }

        # Check existing columns
        existing_cols_result = db.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name='wallet_passes'"
        ))
        existing_cols = {row[0] for row in existing_cols_result}

        for col, col_type in columns.items():
            if col not in existing_cols:
                print(f"Adding column {col} ({col_type})")
                db.execute(text(f"ALTER TABLE wallet_passes ADD COLUMN {col} {col_type}"))
            else:
                print(f"Column {col} already exists.")
                
        # Add foreign key for customer_package_id
        fk_check = db.execute(text("""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name='wallet_passes' AND constraint_type='FOREIGN KEY' AND constraint_name='fk_wallet_passes_customer_package_id'
        """)).scalar()
        
        if not fk_check and 'customer_package_id' not in existing_cols:
            print("Adding foreign key for customer_package_id")
            db.execute(text("ALTER TABLE wallet_passes ADD CONSTRAINT fk_wallet_passes_customer_package_id FOREIGN KEY (customer_package_id) REFERENCES customer_packages (id) ON DELETE SET NULL"))

        db.commit()
        print("Migration completed.")
    except Exception as e:
        print(f"Error during migration: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
