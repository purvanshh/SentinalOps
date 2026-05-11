from workers.queues import celery_app


@celery_app.task(name="workers.tasks.ping")
def ping() -> str:
    return "pong"


from workers.tasks import approval_escalation as _approval_escalation  # noqa: E402,F401
from workers.tasks import approval_workflow as _approval_workflow  # noqa: E402,F401
from workers.tasks import incident_pipeline as _incident_pipeline  # noqa: E402,F401
