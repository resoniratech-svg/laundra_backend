import time
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from app.core.logging import logger
from app.core.tenant import get_current_tenant_id

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        duration = (time.time() - start_time) * 1000
        tenant_id = get_current_tenant_id()
        
        logger.info(
            f"Tenant: {tenant_id} | {request.method} {request.url.path} | "
            f"Status: {response.status_code} | Duration: {duration:.2f}ms"
        )
        return response
