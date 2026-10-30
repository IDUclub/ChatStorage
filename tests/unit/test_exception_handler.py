"""Unhandled failures must not expose credentials or internal diagnostics."""

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.common.exceptions.auth import InvalidAudienceError, TokenExpiredError
from app.common.middlewares.exception_handler import ExceptionHandlerMiddleware


def _client(error):
    app = FastAPI()
    app.add_middleware(ExceptionHandlerMiddleware)

    @app.post("/failure")
    async def fail():
        raise error

    return TestClient(app, raise_server_exceptions=False)


def test_unhandled_error_does_not_expose_request_or_exception():
    response = _client(RuntimeError("synthetic backend password")).post(
        "/failure?token=synthetic-query-token",
        headers={
            "Authorization": "Bearer synthetic-user-token",
            "Cookie": "session=synthetic-session",
        },
        json={"password": "synthetic-body-password"},
    )

    assert response.status_code == 500
    assert response.json() == {"message": "Internal server error"}


@pytest.mark.parametrize(
    "error,status_code,payload",
    [
        (TokenExpiredError(), 401, {"message": "Token expired."}),
        (InvalidAudienceError(), 403, {"message": "Invalid token audience."}),
        (HTTPException(404, "Chat not found"), 404, {"detail": "Chat not found"}),
    ],
)
def test_expected_errors_keep_their_status_and_message(error, status_code, payload):
    response = _client(error).post("/failure")

    assert response.status_code == status_code
    assert response.json() == payload
