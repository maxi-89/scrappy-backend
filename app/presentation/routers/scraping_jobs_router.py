from fastapi import APIRouter, BackgroundTasks, Depends

from app.application.services.scraping_job_service import ScrapingJobService
from app.application.workers.scraping_worker import ScrapingWorker
from app.infrastructure.dependencies import (
    get_admin_key,
    get_scraping_job_service,
    get_scraping_worker,
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
    background_tasks: BackgroundTasks,
    _: str = Depends(get_admin_key),
    service: ScrapingJobService = Depends(get_scraping_job_service),
    worker: ScrapingWorker = Depends(get_scraping_worker),
) -> ScrapingJobResponse:
    response = await service.create_job(payload)
    background_tasks.add_task(worker.run_by_id, response.id)
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
