from sqlalchemy import text
from app.core.database import engine

def upgrade_order_table():
    queries = [
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS review_reply VARCHAR(1000)",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS review_hidden BOOLEAN DEFAULT FALSE"
    ]
    
    with engine.begin() as conn:
        for q in queries:
            print(f"Executing: {q}")
            conn.execute(text(q))
    print("[SUCCESS] Orders table schema upgraded with review reply fields successfully!")

if __name__ == "__main__":
    upgrade_order_table()
