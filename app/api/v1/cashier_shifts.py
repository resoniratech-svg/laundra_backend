from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db
from app.dependencies import get_current_admin
from app.models.user import User
from app.models.cashier_shift import CashierShift
from app.schemas.cashier_shift import CashierShiftOpen, CashierShiftClose, CashierShiftOut

router = APIRouter()

@router.get("/current", response_model=Optional[CashierShiftOut])
def get_current_shift(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    # Find any open shift for this company / cashier
    shift = (
        db.query(CashierShift)
        .filter(
            CashierShift.tenant_id == current_admin.tenant_id,
            CashierShift.status == "OPEN"
        )
        .order_by(desc(CashierShift.start_time))
        .first()
    )
    return shift

@router.post("/open", response_model=CashierShiftOut, status_code=status.HTTP_201_CREATED)
def open_shift(
    payload: CashierShiftOpen,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    # Check if there is already an open shift
    existing = (
        db.query(CashierShift)
        .filter(
            CashierShift.tenant_id == current_admin.tenant_id,
            CashierShift.status == "OPEN"
        )
        .first()
    )
    if existing:
        return existing

    new_shift = CashierShift(
        id=uuid4(),
        tenant_id=current_admin.tenant_id,
        cashier_id=current_admin.id,
        cashier_name=current_admin.name or "Cashier",
        start_time=datetime.utcnow(),
        opening_cash=payload.opening_cash,
        cash_sales=Decimal("0.00"),
        card_sales=Decimal("0.00"),
        driver_handovers=Decimal("0.00"),
        cash_expenses=Decimal("0.00"),
        status="OPEN",
        notes=payload.notes
    )
    db.add(new_shift)
    db.commit()
    db.refresh(new_shift)
    return new_shift

@router.post("/close", response_model=CashierShiftOut)
def close_shift(
    payload: CashierShiftClose,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    # Find the current open shift
    shift = (
        db.query(CashierShift)
        .filter(
            CashierShift.tenant_id == current_admin.tenant_id,
            CashierShift.status == "OPEN"
        )
        .order_by(desc(CashierShift.start_time))
        .first()
    )
    if not shift:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active open shift found to close"
        )

    closing_cash = payload.closing_cash
    cash_sales = payload.cash_sales or Decimal("0.00")
    card_sales = payload.card_sales or Decimal("0.00")
    driver_handovers = payload.driver_handovers or Decimal("0.00")
    cash_expenses = payload.cash_expenses or Decimal("0.00")
    
    # Expected Cash in drawer = Opening Float + Cash Sales + Driver Cash - Cash Expenses
    expected_cash = shift.opening_cash + cash_sales + driver_handovers - cash_expenses
    difference = closing_cash - expected_cash

    shift.end_time = datetime.utcnow()
    shift.closing_cash = closing_cash
    shift.expected_cash = expected_cash
    shift.difference = difference
    shift.cash_sales = cash_sales
    shift.card_sales = card_sales
    shift.driver_handovers = driver_handovers
    shift.cash_expenses = cash_expenses
    shift.status = "CLOSED"
    if payload.notes:
        shift.notes = (shift.notes + "\n" + payload.notes) if shift.notes else payload.notes

    db.commit()
    db.refresh(shift)
    return shift

@router.get("", response_model=List[CashierShiftOut])
def list_shifts(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    shifts = (
        db.query(CashierShift)
        .filter(CashierShift.tenant_id == current_admin.tenant_id)
        .order_by(desc(CashierShift.start_time))
        .limit(200)
        .all()
    )
    return shifts
