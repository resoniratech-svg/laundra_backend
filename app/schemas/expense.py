from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from uuid import UUID
from datetime import datetime

class ExpenseBase(BaseModel):
    description: Optional[str] = None
    amount: Optional[Decimal] = None
    category: Optional[str] = None
    source: Optional[str] = None
    date: Optional[str] = None

class ExpenseCreate(ExpenseBase):
    description: str
    amount: Decimal
    category: str
    source: str
    date: str

class ExpenseOut(ExpenseBase):
    id: UUID
    tenant_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True
