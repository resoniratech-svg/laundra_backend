from sqlalchemy import text
from app.core.database import engine

def upgrade_subscription_table():
    queries = [
        "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS trial_start_date DATE",
        "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS trial_end_date DATE"
    ]
    
    with engine.begin() as conn:
        for q in queries:
            print(f"Executing: {q}")
            conn.execute(text(q))
    print("[SUCCESS] Subscriptions table schema upgraded successfully!")

if __name__ == "__main__":
    upgrade_subscription_table()
