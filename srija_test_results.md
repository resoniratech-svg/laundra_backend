# Visual Test Report: 20-Step Workflow for Customer 'Srija'

I have executed the backend logic precisely as built. Here is the step-by-step visual output of the database state, wallet passes, and automated messages.

### 1️⃣ CUSTOMER REGISTRATION
- **Name:** Srija
- **Phone:** +919876543210
- **Customer ID Generated:** `a8c385aa-5fda-4c61-a511-268270777e1e`

### 2️⃣ PACKAGE SELECTION & PAYMENT
- Selected Package: **bulk package**
- Final Paid Amount: **₹49.98**


❌ Error during execution: (psycopg2.errors.ForeignKeyViolation) insert or update on table "customer_packages" violates foreign key constraint "customer_packages_customer_id_fkey"
DETAIL:  Key (customer_id)=(a8c385aa-5fda-4c61-a511-268270777e1e) is not present in table "users".

[SQL: INSERT INTO customer_packages (id, tenant_id, customer_id, package_id, purchase_date, activation_date, expiry_date, total_quantity, used_quantity, package_value, current_balance, used_amount, status, secure_token, apple_wallet_url, google_wallet_url, pass_color) VALUES (%(id)s::UUID, %(tenant_id)s::UUID, %(customer_id)s::UUID, %(package_id)s::UUID, %(purchase_date)s, %(activation_date)s, %(expiry_date)s, %(total_quantity)s, %(used_quantity)s, %(package_value)s, %(current_balance)s, %(used_amount)s, %(status)s, %(secure_token)s, %(apple_wallet_url)s, %(google_wallet_url)s, %(pass_color)s)]
[parameters: {'id': UUID('27dceeda-33e2-4b61-b667-ed1bc4131a00'), 'tenant_id': UUID('2de61f15-8b85-4c31-9c35-8f09a8554077'), 'customer_id': UUID('a8c385aa-5fda-4c61-a511-268270777e1e'), 'package_id': UUID('3d1d9252-3ba8-44d5-936c-068f81922c02'), 'purchase_date': datetime.datetime(2026, 7, 18, 10, 56, 10, 735692), 'activation_date': datetime.datetime(2026, 7, 18, 10, 56, 10, 735692), 'expiry_date': datetime.datetime(2027, 7, 18, 10, 56, 10, 735692), 'total_quantity': 0, 'used_quantity': 0, 'package_value': Decimal('49.98'), 'current_balance': Decimal('49.98'), 'used_amount': 0, 'status': 'ACTIVE', 'secure_token': '69fad6c8-ccd3-43fa-a22b-76183fddc6ba', 'apple_wallet_url': 'https://wallet.apple.com/add/pass/mock_c6fe6b8c', 'google_wallet_url': 'https://pay.google.com/gp/v/save/mock_13a83f9a', 'pass_color': 'GOLD'}]
(Background on this error at: https://sqlalche.me/e/20/gkpj)