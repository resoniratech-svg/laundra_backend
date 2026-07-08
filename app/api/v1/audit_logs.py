from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.dependencies import get_current_admin
from app.models.user import User
from app.models.audit_log import AuditLog
from app.core.tenant import get_current_tenant_id

router = APIRouter()

@router.get("")
def list_audit_logs(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    tenant_id = get_current_tenant_id()
    return db.query(AuditLog).filter(
        AuditLog.tenant_id == tenant_id
    ).order_by(AuditLog.created_at.desc()).all()
