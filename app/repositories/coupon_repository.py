from app.repositories.base_repository import BaseRepository
from app.models.coupon import Coupon

class CouponRepository(BaseRepository[Coupon]):
    def __init__(self):
        super().__init__(Coupon)
