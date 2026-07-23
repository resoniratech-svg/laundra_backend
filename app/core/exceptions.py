import traceback
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.core.logging import logger, sanitize_sensitive_data

class AppException(Exception):
    def __init__(self, message: str, error_code: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code

async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.message,
            "error_code": exc.error_code
        }
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "message": "Input validation failed",
            "errors": exc.errors(),
            "error_code": "VALIDATION_FAILED"
        }
    )

async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    sanitized_msg = sanitize_sensitive_data(str(exc))
    logger.error(f"[DEBUG DATABASE ERROR] Path: {request.url.path} | Error: {sanitized_msg}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": f"A database error occurred: {sanitized_msg}",
            "error_code": "DATABASE_ERROR"
        }
    )

async def generic_exception_handler(request: Request, exc: Exception):
    sanitized_msg = sanitize_sensitive_data(str(exc))
    logger.error(f"[DEBUG SERVER ERROR] Path: {request.url.path} | Error: {sanitized_msg}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": f"An unexpected server error occurred: {sanitized_msg}",
            "error_code": "INTERNAL_SERVER_ERROR"
        }
    )
