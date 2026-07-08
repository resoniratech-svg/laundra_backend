from app.repositories.base_repository import BaseRepository
from app.models.customer import Customer

class CustomerRepository(BaseRepository[Customer]):
    def __init__(self):
        super().__init__(Customer)
