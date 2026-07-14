from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import uuid4, UUID
from decimal import Decimal
from pydantic import BaseModel

from app.core.database import get_db
from app.dependencies import get_current_admin
from app.models.user import User
from app.schemas.expense import ExpenseCreate, ExpenseOut
from app.repositories.expense_repository import ExpenseRepository

router = APIRouter()
expense_repo = ExpenseRepository()

class ExpenseUpdate(BaseModel):
    description: Optional[str] = None
    amount: Optional[Decimal] = None
    category: Optional[str] = None
    source: Optional[str] = None
    date: Optional[str] = None

@router.post("", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
def create_expense(
    expense_in: ExpenseCreate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    obj_data = expense_in.model_dump()
    obj_data["id"] = uuid4()
    obj_data["tenant_id"] = current_admin.tenant_id
    
    return expense_repo.create(db, obj_in=obj_data)

@router.get("", response_model=List[ExpenseOut])
def list_expenses(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return expense_repo.get_multi(db, tenant_id=current_admin.tenant_id)

@router.put("/{id}", response_model=ExpenseOut)
def update_expense(
    id: UUID,
    payload: ExpenseUpdate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    expense = expense_repo.get(db, id, tenant_id=current_admin.tenant_id)
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found"
        )
    update_data = payload.model_dump(exclude_unset=True)
    return expense_repo.update(db, db_obj=expense, obj_in=update_data)

@router.delete("/{id}", status_code=status.HTTP_200_OK)
def delete_expense(
    id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    expense = expense_repo.get(db, id, tenant_id=current_admin.tenant_id)
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found"
        )
    expense_repo.remove(db, id=id, tenant_id=current_admin.tenant_id)
    return {"success": True, "message": "Expense deleted successfully"}
