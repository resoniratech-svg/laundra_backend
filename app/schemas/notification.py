from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime

class NotificationBase(BaseModel):
    title: str
    message: str
    user_id: Optional[UUID] = None

class NotificationCreate(NotificationBase):
    pass

class NotificationOut(NotificationBase):
    id: UUID
    tenant_id: UUID
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True
