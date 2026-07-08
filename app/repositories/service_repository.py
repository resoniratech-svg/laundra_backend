from app.repositories.base_repository import BaseRepository
from app.models.service import Service

class ServiceRepository(BaseRepository[Service]):
    def __init__(self):
        super().__init__(Service)
