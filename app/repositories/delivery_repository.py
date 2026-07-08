from app.repositories.base_repository import BaseRepository
from app.models.delivery import Delivery

class DeliveryRepository(BaseRepository[Delivery]):
    def __init__(self):
        super().__init__(Delivery)
