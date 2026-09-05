from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from uuid import UUID
from datetime import datetime

class CashierShiftBase(BaseModel):
    opening_cash: Decimal = Decimal("0.00")
    notes: Optional[str] = None

class CashierShiftOpen(CashierShiftBase):
    opening_cash: Decimal
    notes: Optional[str] = None

class CashierShiftClose(BaseModel):
    closing_cash: Decimal
    cash_sales: Optional[Decimal] = Decimal("0.00")
    card_sales: Optional[Decimal] = Decimal("0.00")
    driver_handovers: Optional[Decimal] = Decimal("0.00")
    cash_expenses: Optional[Decimal] = Decimal("0.00")
    expected_cash: Optional[Decimal] = Decimal("0.00")
    notes: Optional[str] = None

class CashierShiftOut(BaseModel):
    id: UUID
    tenant_id: UUID
    cashier_id: Optional[UUID] = None
    cashier_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    opening_cash: Decimal
    closing_cash: Optional[Decimal] = None
    expected_cash: Optional[Decimal] = None
    difference: Optional[Decimal] = None
    cash_sales: Decimal
    card_sales: Decimal
    driver_handovers: Decimal
    cash_expenses: Decimal
    status: str
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
