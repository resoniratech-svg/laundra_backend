import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(os.getenv("DATABASE_URL"))
conn.autocommit = True
cur = conn.cursor()

# List all CUSTOMER role users
cur.execute("SELECT id, name, phone, email, role, status FROM users WHERE role = 'CUSTOMER';")
rows = cur.fetchall()
print("CUSTOMER users found:", len(rows))
for r in rows:
    print(r)

# Delete them all
if rows:
    ids = [str(r[0]) for r in rows]
    cur.execute("DELETE FROM users WHERE role = 'CUSTOMER';")
    print("\nDeleted all CUSTOMER users.")

cur.execute("SELECT COUNT(*) FROM users WHERE role = 'CUSTOMER';")
print("Remaining CUSTOMER users:", cur.fetchone()[0])
conn.close()
