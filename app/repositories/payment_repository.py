from app.repositories.base_repository import BaseRepository
from app.models.payment import Payment

class PaymentRepository(BaseRepository[Payment]):
    def __init__(self):
        super().__init__(Payment)
