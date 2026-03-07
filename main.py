from dotenv import load_dotenv

load_dotenv()  # No-op in cloud environments where vars are already set

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mangum import Mangum

from app.infrastructure.errors.app_error import AppError
from app.infrastructure.errors.domain_validation_error import DomainValidationError
from app.presentation.routers import offers_router, orders_router, public_offers_router, scraping_jobs_router

app = FastAPI(title="Scrappy API", version="1.0.0")


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": str(exc)})


@app.exception_handler(DomainValidationError)
async def domain_validation_error_handler(
    request: Request, exc: DomainValidationError
) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": str(exc)})


app.include_router(public_offers_router.router, prefix="/offers", tags=["offers"])
app.include_router(orders_router.router, prefix="/orders", tags=["orders"])
app.include_router(offers_router.router, prefix="/admin/offers", tags=["admin"])
app.include_router(
    scraping_jobs_router.router,
    prefix="/admin/scraping-jobs",
    tags=["admin"],
)

# AWS Lambda handler
handler = Mangum(app, lifespan="off")
