from sqlalchemy import text
from app.core.database import engine

def upgrade_order_table():
    queries = [
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS rating INTEGER",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS review VARCHAR(1000)"
    ]
    
    with engine.begin() as conn:
        for q in queries:
            print(f"Executing: {q}")
            conn.execute(text(q))
    print("[SUCCESS] Orders table schema upgraded successfully!")

if __name__ == "__main__":
    upgrade_order_table()
