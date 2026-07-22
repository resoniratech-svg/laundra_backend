import sys
from sqlalchemy import text
from app.core.database import SessionLocal, engine

db = SessionLocal()
cols = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='wallet_passes'")).fetchall()
print([c[0] for c in cols])
db.close()
