import psycopg2

conn = psycopg2.connect("postgresql://postgres:postgres@localhost:5433/laundry-backend")
cur = conn.cursor()

queries = [
    "ALTER TABLE customer_packages ADD COLUMN IF NOT EXISTS package_value NUMERIC(10, 2) DEFAULT 0.0;",
    "ALTER TABLE customer_packages ADD COLUMN IF NOT EXISTS current_balance NUMERIC(10, 2) DEFAULT 0.0;",
    "ALTER TABLE customer_packages ADD COLUMN IF NOT EXISTS used_amount NUMERIC(10, 2) DEFAULT 0.0;",
    "ALTER TABLE customer_packages ADD COLUMN IF NOT EXISTS apple_wallet_url VARCHAR(255);",
    "ALTER TABLE customer_packages ADD COLUMN IF NOT EXISTS google_wallet_url VARCHAR(255);",
    "ALTER TABLE customer_packages ADD COLUMN IF NOT EXISTS pass_color VARCHAR(20) DEFAULT 'GOLD';",
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS applied_package_id UUID REFERENCES customer_packages(id);"
]

for q in queries:
    try:
        cur.execute(q)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print("Query failed:", q, "\nError:", e)

cur.close()
conn.close()
print("Migration completed.")
