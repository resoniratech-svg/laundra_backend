from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from uuid import UUID
from app.core.tenant import set_current_tenant_id
from jose import jwt

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        tenant_id_header = request.headers.get("X-Tenant-ID")
        tenant_id = None
        if tenant_id_header:
            try:
                tenant_id = UUID(tenant_id_header)
            except ValueError:
                pass
                
        if not tenant_id:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                try:
                    payload = jwt.get_unverified_claims(token)
                    tenant_id_str = payload.get("tenant_id")
                    if tenant_id_str and tenant_id_str != "None":
                        tenant_id = UUID(tenant_id_str)
                except Exception:
                    pass
        
        set_current_tenant_id(tenant_id)
        response = await call_next(request)
        return response
