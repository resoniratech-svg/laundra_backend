
import sys
import traceback
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import get_db, engine
from app.models.user import User
from sqlalchemy import text
from app.dependencies import get_current_user
import uuid

client = TestClient(app)

with engine.connect() as conn:
    res = conn.execute(text('SELECT id FROM users WHERE role=''CUSTOMER'' LIMIT 1'))
    customer_id = res.scalar() or uuid.uuid4()
    
    res = conn.execute(text('SELECT id FROM users WHERE role=''ADMIN'' LIMIT 1'))
    admin_id = res.scalar()

with get_db() as db:
    admin_user = db.query(User).filter(User.id == admin_id).first()

app.dependency_overrides[get_current_user] = lambda: admin_user

try:
    response = client.get(f'/api/v1/prepaid-packages/customer/{customer_id}', headers={'Origin': 'https://laundry-project-laundry-frontend.cocjl5.easypanel.host'})
    print('STATUS:', response.status_code)
    print('HEADERS:', response.headers.get('access-control-allow-origin'))
    if response.status_code >= 400:
        print('ERROR JSON:', response.text)
except Exception as e:
    traceback.print_exc()
