from pydantic import BaseModel
from uuid import UUID
from decimal import Decimal
from datetime import datetime

class InvoiceOut(BaseModel):
    id: UUID
    tenant_id: UUID
    order_id: UUID
    invoice_number: str
    amount: Decimal
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
