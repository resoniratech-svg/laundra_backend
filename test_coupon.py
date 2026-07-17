from fastapi.testclient import TestClient
from app.main import app
from uuid import uuid4
from datetime import date
import sys

client = TestClient(app)
payload = {
    "name": "speacial",
    "code": "123",
    "discount_type": "PERCENTAGE",
    "value": 0,
    "start_date": "2026-07-17",
    "expiry_date": "2026-07-18",
    "required_services": [
        {"service_id": str(uuid4()), "qty": 1, "name": "Thobe", "price": 3.0}
    ]
}

from app.dependencies import get_current_admin
from app.models.user import User

def override_get_current_admin():
    user = User()
    user.id = uuid4()
    user.tenant_id = uuid4()
    user.email = "admin@example.com"
    return user

app.dependency_overrides[get_current_admin] = override_get_current_admin

try:
    response = client.post("/api/v1/coupons", json=payload)
    print("STATUS:", response.status_code)
    print("BODY:", response.json())
except Exception as e:
    print("EXCEPTION:", e)
