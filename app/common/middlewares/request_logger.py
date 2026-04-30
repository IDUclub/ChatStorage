"""Request logging middleware."""

from time import perf_counter

from fastapi import FastAPI, Request
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log incoming requests and outgoing responses."""

    def __init__(self, app: FastAPI):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        started_at = perf_counter()
        method = request.method
        path = request.url.path
        query = str(request.url.query)
        client = request.client.host if request.client else "unknown"

        logger.info(
            "Incoming request: method={} path={} query={} client={}",
            method,
            path,
            query,
            client,
        )

        response = await call_next(request)
        duration_ms = (perf_counter() - started_at) * 1000

        log_message = (
            "Request finished: method={} path={} status_code={} "
            "duration_ms={:.2f} client={}"
        )
        log_args = (method, path, response.status_code, duration_ms, client)

        if response.status_code >= 500:
            logger.error(log_message, *log_args)
        elif response.status_code >= 400:
            logger.warning(log_message, *log_args)
        else:
            logger.info(log_message, *log_args)

        return response
