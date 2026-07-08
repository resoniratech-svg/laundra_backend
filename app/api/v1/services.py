from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import uuid4, UUID
from app.core.database import get_db
from app.dependencies import get_current_user, get_current_admin, get_current_super_admin
from app.models.user import User
from app.schemas.service import ServiceCreate, ServiceOut
from app.repositories.service_repository import ServiceRepository

router = APIRouter()
service_repo = ServiceRepository()

@router.post("", response_model=ServiceOut, status_code=status.HTTP_201_CREATED)
def create_service(
    service_in: ServiceCreate,
    current_super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    obj_data = service_in.model_dump()
    obj_data["id"] = uuid4()
    
    return service_repo.create(db, obj_in=obj_data)

@router.get("", response_model=List[ServiceOut])
def list_services(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return service_repo.get_multi(db, tenant_id=current_user.tenant_id)

@router.put("/{id}", response_model=ServiceOut)
def update_service(
    id: UUID,
    service_in: ServiceCreate,
    current_super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    service = service_repo.get(db, id, tenant_id=service_in.tenant_id)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found"
        )
    return service_repo.update(db, db_obj=service, obj_in=service_in.model_dump())

@router.delete("/{id}", response_model=ServiceOut)
def delete_service(
    id: UUID,
    tenant_id: UUID,
    current_super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    service = service_repo.get(db, id, tenant_id=tenant_id)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found"
        )
    return service_repo.remove(db, id=id, tenant_id=tenant_id)
