from app.repositories.base_repository import BaseRepository
from app.models.company import Company

class CompanyRepository(BaseRepository[Company]):
    def __init__(self):
        super().__init__(Company)
