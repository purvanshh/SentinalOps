from celery import Celery

from core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "sentinelops",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
