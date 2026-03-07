import asyncio

from fastapi import APIRouter, Depends

from app.application.services.scraping_job_service import ScrapingJobService
from app.infrastructure.aws.sfn_client import SfnStarterClient
from app.infrastructure.dependencies import (
    get_admin_key,
    get_scraping_job_service,
    get_sfn_client,
)
from app.infrastructure.errors.app_error import AppError
from app.presentation.schemas.scraping_job_schemas import (
    CreateScrapingJobRequest,
    ScrapingJobResponse,
)

router = APIRouter()


@router.post("", response_model=ScrapingJobResponse, status_code=202)
async def create_scraping_job(
    payload: CreateScrapingJobRequest,
    _: str = Depends(get_admin_key),
    service: ScrapingJobService = Depends(get_scraping_job_service),
    sfn: SfnStarterClient = Depends(get_sfn_client),
) -> ScrapingJobResponse:
    response = await service.create_job(payload)
    await asyncio.to_thread(sfn.start_execution, response.id)
    return response


@router.get("", response_model=list[ScrapingJobResponse])
async def list_scraping_jobs(
    status: str | None = None,
    _: str = Depends(get_admin_key),
    service: ScrapingJobService = Depends(get_scraping_job_service),
) -> list[ScrapingJobResponse]:
    return await service.list_jobs(status=status)


@router.get("/{job_id}", response_model=ScrapingJobResponse)
async def get_scraping_job(
    job_id: str,
    _: str = Depends(get_admin_key),
    service: ScrapingJobService = Depends(get_scraping_job_service),
) -> ScrapingJobResponse:
    job = await service.get_job(job_id)
    if job is None:
        raise AppError("Scraping job not found", status_code=404)
    return job
