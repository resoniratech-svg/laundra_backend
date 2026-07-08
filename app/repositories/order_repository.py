from app.repositories.base_repository import BaseRepository
from app.models.order import Order

class OrderRepository(BaseRepository[Order]):
    def __init__(self):
        super().__init__(Order)
