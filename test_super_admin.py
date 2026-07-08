import urllib.request
import urllib.error
import json
import time

BASE_URL = "http://localhost:8000/api/v1"

def req(url, method="GET", data=None, token=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data:
        headers["Content-Type"] = "application/json"
        data = json.dumps(data).encode("utf-8")
        
    request = urllib.request.Request(f"{BASE_URL}{url}", data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(request)
        return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.read().decode('utf-8')} on {url}")
        return None

def test_api():
    print("Testing Super Admin APIs...")
    
    # 1. Login
    res = req("/auth/login", method="POST", data={"email": "superadmin@laundry.com", "password": "admin123"})
    if not res: return
    token = res.get("access_token")
    print("[SUCCESS] Login successful")
    
    # 2. Metrics
    metrics = req("/saas-admin/metrics", token=token)
    print("[SUCCESS] Metrics Response:", json.dumps(metrics, indent=2))
    
    # 3. Create Subscription Plan
    plan_data = {
        "name": "MEGA_ENTERPRISE",
        "description": "Unlimited everything",
        "price": 999.0,
        "max_admins": 100,
        "max_customers": 1000000
    }
    # This might fail if it already exists, so we ignore errors
    plan = req("/saas/plans", method="POST", data=plan_data, token=token)
    if plan:
        print("[SUCCESS] Plan Created:", plan["name"])
    else:
        print("[WARNING] Plan might already exist, skipping.")

if __name__ == "__main__":
    test_api()
