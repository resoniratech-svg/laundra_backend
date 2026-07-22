
from app.core.database import SessionLocal
from app.models.customer_package import CustomerPackage
db = SessionLocal()
pkg = db.query(CustomerPackage).first()
if pkg:
    print('CUSTOMER_ID:', pkg.customer_id)
else:
    print('NO PACKAGES')
