from sqlalchemy import text
from app.core.database import engine

def create_address_and_referral():
    queries = [
        """
        CREATE TABLE IF NOT EXISTS customer_addresses (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL,
            customer_id UUID NOT NULL,
            label VARCHAR(100) NOT NULL,
            address_line TEXT NOT NULL,
            is_default BOOLEAN DEFAULT FALSE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            FOREIGN KEY(tenant_id) REFERENCES companies(id) ON DELETE CASCADE,
            FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE CASCADE
        )
        """,
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS referral_code VARCHAR(50)",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS referred_by_id UUID REFERENCES customers(id) ON DELETE SET NULL"
    ]
    
    with engine.begin() as conn:
        for q in queries:
            print("Executing query...")
            conn.execute(text(q))
    print("[SUCCESS] Customer Address and Referral columns created successfully!")

if __name__ == "__main__":
    create_address_and_referral()
