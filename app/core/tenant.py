import contextvars
from uuid import UUID
from typing import Optional

_tenant_id_ctx = contextvars.ContextVar[Optional[UUID]]("tenant_id", default=None)

def get_current_tenant_id() -> Optional[UUID]:
    return _tenant_id_ctx.get()

def set_current_tenant_id(tenant_id: Optional[UUID]) -> None:
    _tenant_id_ctx.set(tenant_id)
