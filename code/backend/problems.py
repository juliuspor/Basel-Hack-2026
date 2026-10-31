"""Errors as RFC 9457 problem details, the same shape on every endpoint."""

from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

PROBLEM_JSON = "application/problem+json"


class Problem(Exception):
    """An error the API answers with a problem details body."""

    def __init__(self, status: HTTPStatus, detail: str, headers: dict[str, str] | None = None) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.headers = headers


def problem_response(status: int, detail: str, headers: dict[str, str] | None = None) -> JSONResponse:
    body = {"type": "about:blank", "title": HTTPStatus(status).phrase, "status": status, "detail": detail}
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON, headers=headers)


def install(app: FastAPI) -> None:
    """Answers our own errors, FastAPI's validation errors and unknown routes as problem details."""

    @app.exception_handler(Problem)
    async def problem(request: Request, error: Problem) -> JSONResponse:
        return problem_response(error.status, error.detail, error.headers)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> JSONResponse:
        return problem_response(error.status_code, str(error.detail), error.headers)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError) -> JSONResponse:
        detail = ". ".join(
            f"{'.'.join(str(part) for part in issue['loc'])}: {issue['msg']}" for issue in error.errors()
        )
        return problem_response(HTTPStatus.UNPROCESSABLE_CONTENT, detail)
