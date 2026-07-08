from sqlalchemy import text
from app.core.database import engine

def upgrade_user_table():
    queries = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_photo VARCHAR(500)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS vehicle_type VARCHAR(100)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS vehicle_number VARCHAR(100)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS license_number VARCHAR(100)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS aadhaar_number VARCHAR(100)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS address VARCHAR(500)"
    ]
    
    with engine.begin() as conn:
        for q in queries:
            print(f"Executing: {q}")
            conn.execute(text(q))
    print("[SUCCESS] Users table schema upgraded successfully!")

if __name__ == "__main__":
    upgrade_user_table()
