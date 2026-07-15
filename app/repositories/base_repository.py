from typing import Generic, TypeVar, Type, List, Optional, Any
from sqlalchemy.orm import Session
from uuid import UUID
from app.core.tenant import get_current_tenant_id

ModelType = TypeVar("ModelType")

class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model

    def get_query(self, db: Session, tenant_id: Optional[UUID] = None):
        query = db.query(self.model)
        if hasattr(self.model, "tenant_id"):
            if not tenant_id:
                tenant_id = get_current_tenant_id()
            if tenant_id:
                query = query.filter(self.model.tenant_id == tenant_id)
        return query

    def get(self, db: Session, id: Any, tenant_id: Optional[UUID] = None) -> Optional[ModelType]:
        return self.get_query(db, tenant_id).filter(self.model.id == id).first()

    def get_multi(self, db: Session, *, skip: int = 0, limit: int = 10000, tenant_id: Optional[UUID] = None) -> List[ModelType]:
        return self.get_query(db, tenant_id).offset(skip).limit(limit).all()

    def create(self, db: Session, *, obj_in: dict) -> ModelType:
        db_obj = self.model(**obj_in)
        if hasattr(self.model, "tenant_id") and not getattr(db_obj, "tenant_id", None):
            tenant_id = get_current_tenant_id()
            if tenant_id:
                db_obj.tenant_id = tenant_id
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, *, db_obj: ModelType, obj_in: dict) -> ModelType:
        for field in obj_in:
            if hasattr(db_obj, field):
                setattr(db_obj, field, obj_in[field])
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def remove(self, db: Session, *, id: Any, tenant_id: Optional[UUID] = None) -> Optional[ModelType]:
        obj = self.get(db, id, tenant_id)
        if obj:
            db.delete(obj)
            db.commit()
        return obj
