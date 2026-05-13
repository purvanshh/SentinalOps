from celery import Celery
from core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "sentinelops",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    # Acknowledge only after successful completion; re-deliver on worker crash
    task_acks_late=True,
    reject_on_worker_lost=True,
    # Prevent a single worker from monopolising the queue during burst load
    worker_prefetch_multiplier=1,
    task_default_retry_delay=5,
    # Serialization — restrict to JSON to prevent deserialization attacks
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Stuck-task detection: raise SoftTimeLimitExceeded at 5 min, hard kill at 6 min
    task_soft_time_limit=300,
    task_time_limit=360,
    # Task routing — dead-letter queues receive poison messages for operator inspection
    task_routes={
        "workers.tasks.run_incident_pipeline": {"queue": "incidents"},
        "workers.tasks.replay_pending_incidents": {"queue": "incidents"},
        "workers.tasks.escalate_approval": {"queue": "approvals"},
        "workers.schedulers.scan_pending_approvals": {"queue": "approvals"},
    },
)
celery_app.autodiscover_tasks(
    ["workers.tasks", "workers.schedulers"], related_name=None, force=True
)
