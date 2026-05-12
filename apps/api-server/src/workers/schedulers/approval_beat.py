from celery.schedules import crontab

from workers.queues import celery_app


celery_app.conf.beat_schedule = {
    "scan-pending-approvals": {
        "task": "workers.schedulers.scan_pending_approvals",
        "schedule": crontab(minute="*/5"),
    },
    "replay-pending-incidents": {
        "task": "workers.tasks.replay_pending_incidents",
        "schedule": 10.0,
    },
}
