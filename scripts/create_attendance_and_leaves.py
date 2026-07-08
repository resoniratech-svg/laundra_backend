from sqlalchemy import text
from app.core.database import engine

def create_tables():
    queries = [
        """
        CREATE TABLE IF NOT EXISTS attendance (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL,
            user_id UUID NOT NULL,
            clock_in TIMESTAMP WITH TIME ZONE NOT NULL,
            clock_out TIMESTAMP WITH TIME ZONE,
            gps_lat_in DOUBLE PRECISION,
            gps_lng_in DOUBLE PRECISION,
            gps_lat_out DOUBLE PRECISION,
            gps_lng_out DOUBLE PRECISION,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            FOREIGN KEY(tenant_id) REFERENCES companies(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS leave_requests (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL,
            user_id UUID NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            reason VARCHAR(1000) NOT NULL,
            status VARCHAR(50) NOT NULL,
            admin_comment VARCHAR(1000),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            FOREIGN KEY(tenant_id) REFERENCES companies(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    ]
    
    with engine.begin() as conn:
        for q in queries:
            print("Executing query...")
            conn.execute(text(q))
    print("[SUCCESS] Attendance and Leave Requests tables created successfully!")

if __name__ == "__main__":
    create_tables()
