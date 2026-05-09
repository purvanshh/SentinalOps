from celery import Celery

from core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "sentinelops",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_retry_delay=5,
    task_routes={
        "workers.tasks.run_incident_pipeline": {"queue": "incidents"},
        "workers.tasks.replay_pending_incidents": {"queue": "incidents"},
        "workers.tasks.escalate_approval": {"queue": "approvals"},
        "workers.schedulers.scan_pending_approvals": {"queue": "approvals"},
    },
)
