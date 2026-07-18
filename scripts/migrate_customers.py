import psycopg2
from psycopg2.extras import RealDictCursor

def migrate():
    # Connect directly to the database
    conn = psycopg2.connect("postgresql://postgres:postgres@localhost:5433/laundry-backend")
    conn.autocommit = True
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    print("Starting manual migration for missing customer fields...")
    
    try:
        # Check if columns exist, if not, add them
        
        cursor.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS gender VARCHAR(20);")
        print("Added gender column.")
        
        cursor.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS dob VARCHAR(50);")
        print("Added dob column.")
        
        cursor.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS gst_number VARCHAR(50);")
        print("Added gst_number column.")
        
        cursor.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS notes TEXT;")
        print("Added notes column.")
        
        print("Migration complete!")
        
    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    migrate()
