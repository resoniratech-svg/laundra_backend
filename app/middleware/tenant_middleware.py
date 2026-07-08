from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from uuid import UUID
from app.core.tenant import set_current_tenant_id

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        tenant_id_header = request.headers.get("X-Tenant-ID")
        tenant_id = None
        if tenant_id_header:
            try:
                tenant_id = UUID(tenant_id_header)
            except ValueError:
                pass
        
        set_current_tenant_id(tenant_id)
        response = await call_next(request)
        return response
