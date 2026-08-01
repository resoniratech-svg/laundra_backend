import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app

def test_endpoint():
    client = TestClient(app)
    token = "bec30273-aa6f-45a3-bba7-16068a11f008"
    
    print(f"\n[+] Testing GET /api/v1/wallet/google/pass/{token}")
    res = client.get(f"/api/v1/wallet/google/pass/{token}", follow_redirects=False)
    
    print(f"[+] Status Code: {res.status_code}")
    if res.status_code == 307:
        print(f"[OK] HTTP 307 Redirect Success!")
        print(f"     Location: {res.headers.get('location')[:60]}...[REDACTED_JWT]")
    else:
        print(f"[x] Error Response Body: {res.json()}")

if __name__ == "__main__":
    test_endpoint()
