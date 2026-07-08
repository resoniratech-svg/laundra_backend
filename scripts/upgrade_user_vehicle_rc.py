from sqlalchemy import text
from app.core.database import engine

def upgrade_user_table():
    queries = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS vehicle_rc VARCHAR(500)"
    ]
    
    with engine.begin() as conn:
        for q in queries:
            print(f"Executing: {q}")
            conn.execute(text(q))
    print("[SUCCESS] Users table schema upgraded with vehicle_rc successfully!")

if __name__ == "__main__":
    upgrade_user_table()
