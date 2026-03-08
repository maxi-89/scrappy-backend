import os

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.offer_service import OfferService
from app.application.services.order_service import OrderService
from app.application.services.scraping_job_service import ScrapingJobService
from app.application.services.user_service import UserService
from app.application.services.webhook_service import StripeWebhookService
from app.domain.models.current_user import CurrentUser
from app.domain.repositories.i_offer_repository import IOfferRepository
from app.domain.repositories.i_order_repository import IOrderRepository
from app.domain.repositories.i_pricing_repository import IPricingRepository
from app.domain.repositories.i_scraping_job_repository import IScrapingJobRepository
from app.domain.repositories.i_user_repository import IUserRepository
from app.infrastructure.auth.auth0_jwt_verifier import verify_token
from app.infrastructure.aws.sfn_client import SfnStarterClient
from app.infrastructure.database.session import get_db_session
from app.infrastructure.errors.app_error import AppError
from app.infrastructure.repositories.offer_repository import OfferRepository
from app.infrastructure.repositories.order_repository import OrderRepository
from app.infrastructure.repositories.pricing_repository import PricingRepository
from app.infrastructure.repositories.scraping_job_repository import ScrapingJobRepository
from app.infrastructure.repositories.user_repository import UserRepository
from app.infrastructure.stripe.stripe_client import IStripeClient, StripeClient

_ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "")

_bearer_scheme = HTTPBearer(auto_error=False)


def get_user_repository(
    session: AsyncSession = Depends(get_db_session),
) -> IUserRepository:
    return UserRepository(session)


def get_user_service(
    repository: IUserRepository = Depends(get_user_repository),
) -> UserService:
    return UserService(repository)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    user_service: UserService = Depends(get_user_service),
) -> CurrentUser:
    if credentials is None:
        raise AppError("Missing authentication token", status_code=401)
    current_user = verify_token(credentials.credentials)
    local_user = await user_service.sync_user(current_user)
    return CurrentUser(sub=current_user.sub, email=current_user.email, user_id=local_user.id)


def get_admin_key(x_admin_key: str = Header(...)) -> str:
    if not _ADMIN_API_KEY or x_admin_key != _ADMIN_API_KEY:
        raise AppError("Invalid or missing admin key", status_code=401)
    return x_admin_key


def get_scraping_job_repository(
    session: AsyncSession = Depends(get_db_session),
) -> IScrapingJobRepository:
    return ScrapingJobRepository(session)


def get_scraping_job_service(
    repository: IScrapingJobRepository = Depends(get_scraping_job_repository),
) -> ScrapingJobService:
    return ScrapingJobService(repository)


def get_sfn_client() -> SfnStarterClient:
    return SfnStarterClient()


def get_offer_repository(
    session: AsyncSession = Depends(get_db_session),
) -> IOfferRepository:
    return OfferRepository(session)


def get_pricing_repository(
    session: AsyncSession = Depends(get_db_session),
) -> IPricingRepository:
    return PricingRepository(session)


def get_offer_service(
    repository: IOfferRepository = Depends(get_offer_repository),
    pricing_repository: IPricingRepository = Depends(get_pricing_repository),
) -> OfferService:
    return OfferService(repository, pricing_repository)


def get_order_repository(
    session: AsyncSession = Depends(get_db_session),
) -> IOrderRepository:
    return OrderRepository(session)


def get_stripe_client() -> IStripeClient:
    return StripeClient()


def get_order_service(
    order_repository: IOrderRepository = Depends(get_order_repository),
    offer_repository: IOfferRepository = Depends(get_offer_repository),
    pricing_repository: IPricingRepository = Depends(get_pricing_repository),
    stripe_client: IStripeClient = Depends(get_stripe_client),
) -> OrderService:
    return OrderService(order_repository, offer_repository, pricing_repository, stripe_client)


_STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")


def get_webhook_service(
    order_repository: IOrderRepository = Depends(get_order_repository),
    offer_repository: IOfferRepository = Depends(get_offer_repository),
    scraping_job_repository: IScrapingJobRepository = Depends(get_scraping_job_repository),
    stripe_client: IStripeClient = Depends(get_stripe_client),
    sfn_client: SfnStarterClient = Depends(get_sfn_client),
) -> StripeWebhookService:
    return StripeWebhookService(
        stripe_client=stripe_client,
        order_repository=order_repository,
        offer_repository=offer_repository,
        scraping_job_repository=scraping_job_repository,
        sfn_client=sfn_client,
        webhook_secret=_STRIPE_WEBHOOK_SECRET,
    )
