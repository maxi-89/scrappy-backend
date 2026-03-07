from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mangum import Mangum

from app.infrastructure.errors.app_error import AppError
from app.infrastructure.errors.domain_validation_error import DomainValidationError
from app.presentation.routers import orders_router

app = FastAPI(title="Scrappy API", version="1.0.0")


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": str(exc)})


@app.exception_handler(DomainValidationError)
async def domain_validation_error_handler(
    request: Request, exc: DomainValidationError
) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": str(exc)})


app.include_router(orders_router.router, prefix="/orders", tags=["orders"])

# AWS Lambda handler
handler = Mangum(app, lifespan="off")
