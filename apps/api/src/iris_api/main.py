"""IRIS API application."""

from http import HTTPStatus

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="IRIS API")


class HealthResponse(BaseModel):
    status: str


@app.get(
    "/healthz",
    response_model=HealthResponse,
    status_code=HTTPStatus.OK,
    summary="Health check",
)
async def healthz() -> HealthResponse:
    return HealthResponse(status="ok")
