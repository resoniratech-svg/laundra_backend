from app.repositories.base_repository import BaseRepository
from app.models.coupon import Coupon
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import date

class CouponRepository(BaseRepository[Coupon]):
    def __init__(self):
        super().__init__(Coupon)

    def get_active_multi(self, db: Session, tenant_id: UUID):
        today = date.today()
        return db.query(self.model).filter(
            self.model.tenant_id == tenant_id,
            self.model.start_date <= today,
            self.model.expiry_date >= today
        ).all()
