from workers.queues import celery_app


@celery_app.task(name="workers.tasks.ping")
def ping() -> str:
    return "pong"
