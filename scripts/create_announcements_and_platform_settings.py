from sqlalchemy import text
from app.core.database import engine

def create_new_tables():
    queries = [
        """
        CREATE TABLE IF NOT EXISTS platform_settings (
            id UUID PRIMARY KEY,
            platform_name VARCHAR(255) NOT NULL,
            logo_url VARCHAR(500),
            smtp_host VARCHAR(255),
            smtp_port VARCHAR(20),
            smtp_username VARCHAR(255),
            smtp_password VARCHAR(255),
            sms_api_key VARCHAR(255),
            whatsapp_api_key VARCHAR(255),
            google_maps_api_key VARCHAR(255),
            payment_gateway_client_id VARCHAR(255),
            payment_gateway_secret VARCHAR(255),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS announcements (
            id UUID PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            content TEXT NOT NULL,
            status VARCHAR(50) NOT NULL,
            target_companies TEXT,
            scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        )
        """
    ]
    
    with engine.begin() as conn:
        for q in queries:
            print("Executing query...")
            conn.execute(text(q))
    print("[SUCCESS] New tables created successfully!")

if __name__ == "__main__":
    create_new_tables()
