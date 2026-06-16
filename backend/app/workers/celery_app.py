from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery = Celery("doc_hub", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule_filename="/tmp/celerybeat-schedule",
    imports=(
        "app.workers.ingest_task",
        "app.workers.sync_task",
    ),
    beat_schedule={
        "nightly-notion-sync": {
            "task": "app.workers.sync_task.sync_all_notion",
            "schedule": crontab(hour=2, minute=0),
        },
    },
)
