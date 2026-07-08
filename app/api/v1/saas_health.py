from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db, engine
from app.dependencies import get_current_user
from app.models.user import User
import psutil

router = APIRouter()

def get_current_super_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only SaaS super administrators can access this resource"
        )
    return current_user

@router.get("")
def get_system_health(
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    db_status = "unhealthy"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            db_status = "healthy"
    except Exception:
        pass
        
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "cpu_usage_percent": psutil.cpu_percent(),
        "memory_usage_percent": psutil.virtual_memory().percent,
        "disk_usage_percent": psutil.disk_usage('/').percent
    }

@router.post("/backup")
def trigger_database_backup(
    super_admin: User = Depends(get_current_super_admin),
):
    # In a real environment, this would trigger an async celery task to run pg_dump
    # For now, we mock the response as requested in the plan.
    return {
        "message": "Database backup triggered successfully.",
        "status": "IN_PROGRESS",
        "mock": True
    }

@router.post("/restore")
def trigger_database_restore(
    backup_file_id: str,
    super_admin: User = Depends(get_current_super_admin),
):
    # Mock restore
    return {
        "message": f"Database restore from {backup_file_id} triggered successfully.",
        "status": "IN_PROGRESS",
        "mock": True
    }
