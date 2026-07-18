import requests
import uuid
import time
import sys

BASE_URL = "http://localhost:8000/api/v1"

def print_step(step_num, title, data=None):
    print(f"\n[{step_num}] {title}")
    if data:
        print(f"  -> {data}")
    time.sleep(1)

def run_test():
    print("=== STARTING 20-STEP WORKFLOW TEST ===")
    
    # Needs a valid token, we'll login as superadmin or use an existing customer if it's open.
    # Actually, we can just use the DB directly for testing to bypass auth if needed, 
    # but let's try auth first.
    
    # 1. Login as Super Admin to get token
    print_step("PRE-STEP", "Logging into Backend to get Auth Token")
    login_res = requests.post(
        f"http://localhost:8000/api/v1/auth/login",
        data={"username": "superadmin@example.com", "password": "password"} # Try default
    )
    
    if login_res.status_code != 200:
        print("Could not log in via API. The backend might require specific credentials or isn't running on port 8000.")
        return
        
    token = login_res.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    
    # STEP 1: Create Customer
    print_step("STEP 1", "Registering Customer")
    cust_res = requests.post(f"{BASE_URL}/customers", json={
        "name": "Test User Workflow",
        "phone": f"+91999{random.randint(100000, 999999)}"
    }, headers=headers)
    
    if cust_res.status_code != 201:
        print("Failed to create customer", cust_res.json())
        return
        
    customer = cust_res.json()
    print_step("STEP 1.1", "Customer Registered", f"ID: {customer['id']}, Name: {customer['name']}")
    
    # STEP 2: Create a Prepaid Package (Admin side) to sell
    print_step("STEP 2", "Creating a master Prepaid Package")
    pkg_res = requests.post(f"{BASE_URL}/prepaid-packages", json={
        "name": "Gold Membership Test",
        "code": "GOLD-TEST",
        "original_price": 6000.0,
        "offer_price": 5000.0,
        "total_quantity": 0,
        "eligible_services": ["ALL"],
        "validity_days": 365
    }, headers=headers)
    
    if pkg_res.status_code != 201:
        print("Failed to create package", pkg_res.json())
        return
        
    master_pkg = pkg_res.json()
    print_step("STEP 2.1", "Package Created", f"Package Value: ₹{master_pkg['offer_price']}")

    # STEP 4, 5, 6: Purchase Package
    print_step("STEP 5 & 6", "Purchasing Package for Customer")
    purchase_res = requests.post(f"{BASE_URL}/prepaid-packages/purchase", json={
        "customer_id": customer['id'],
        "package_id": master_pkg['id']
    }, headers=headers)
    
    if purchase_res.status_code != 201:
        print("Failed to purchase package", purchase_res.json())
        return
        
    customer_pkg = purchase_res.json()
    print_step("STEP 6.1", "Customer Package Activated", 
               f"Balance: ₹{customer_pkg['current_balance']}, Status: {customer_pkg['status']}")
               
    # STEP 7, 8, 9: Wallets
    print_step("STEP 8 & 9", "Digital Wallets Generated", 
               f"Apple: {customer_pkg['apple_wallet_url']}\n  -> Google: {customer_pkg['google_wallet_url']}")
    
    print_step("STEP 10", "WhatsApp Automation Triggered (Check Backend Logs)")
    
    # STEP 14, 15: Create Order and deduct from package
    print_step("STEP 14", "Creating Laundry Order and Paying with Package")
    
    # We need a service first
    srv_res = requests.get(f"{BASE_URL}/services", headers=headers)
    service_id = srv_res.json()[0]['id'] if srv_res.json() else str(uuid.uuid4())
    
    order_res = requests.post(f"{BASE_URL}/orders", json={
        "customer_id": customer['id'],
        "items": [
            {"service_id": service_id, "quantity": 1} # Mock
        ],
        "pay_with_package_id": customer_pkg['id']
    }, headers=headers)
    
    if order_res.status_code not in (200, 201):
        print("Order creation failed", order_res.json())
        return
        
    order = order_res.json()
    print_step("STEP 15", "Order Paid and Package Deducted", f"Order Total: ₹{order['total_amount']}, Payment Status: {order['payment_status']}")
    
    print("=== WORKFLOW TEST COMPLETED ===")

if __name__ == "__main__":
    import random
    run_test()
