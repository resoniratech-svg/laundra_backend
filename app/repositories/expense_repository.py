from app.repositories.base_repository import BaseRepository
from app.models.expense import Expense

class ExpenseRepository(BaseRepository[Expense]):
    def __init__(self):
        super().__init__(Expense)
