import time
import datetime
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

logger = logging.getLogger("http.access")

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        client_ip = request.client.host if request.client else "unknown"
        timestamp = datetime.datetime.utcnow().isoformat()
        path = request.url.path

        if "/wallet/apple" in path:
            auth_present = "authorization" in request.headers
            user_agent = request.headers.get("user-agent", "N/A")
            
            body_str = ""
            if request.method in ["POST", "PUT", "PATCH"]:
                try:
                    body_bytes = await request.body()
                    async def receive():
                        return {"type": "http.request", "body": body_bytes}
                    request._receive = receive
                    body_str = body_bytes.decode("utf-8", errors="ignore")
                except Exception as e_body:
                    body_str = f"<Error reading body: {e_body}>"

            req_log = (
                "========================================================\n"
                "[APPLE REQUEST RECEIVED]\n"
                f"Timestamp: {timestamp}\n"
                f"Method: {request.method}\n"
                f"Full URL: {request.url}\n"
                f"Client IP: {client_ip}\n"
                f"Headers: {dict(request.headers)}\n"
                f"Authorization header present: {auth_present}\n"
                f"User-Agent: {user_agent}\n"
                f"Request Body (if POST): {body_str}\n"
                "========================================================"
            )
            logger.warning(req_log)
            print(req_log, flush=True)

            response = await call_next(request)
            duration = (time.time() - start_time) * 1000

            resp_log = (
                "========================================================\n"
                "[APPLE RESPONSE SENT]\n"
                f"Status Code: {response.status_code}\n"
                f"Execution Time: {duration:.2f}ms\n"
                "========================================================"
            )
            logger.warning(resp_log)
            print(resp_log, flush=True)
            return response

        user_agent = request.headers.get("user-agent", "N/A")
        auth_present = "authorization" in request.headers
        print(f"[FASTAPI INCOMING] IP={client_ip} | {request.method} {request.url} | UserAgent={user_agent} | Auth={'YES' if auth_present else 'NO'}", flush=True)

        response = await call_next(request)
        duration = (time.time() - start_time) * 1000
        
        log_line = (
            f"[HTTP ACCESS] {timestamp} | IP: {client_ip} | {request.method} {request.url.path} | "
            f"Status: {response.status_code} | Duration: {duration:.2f}ms"
        )
        logger.warning(log_line)
        print(log_line, flush=True)
        return response
