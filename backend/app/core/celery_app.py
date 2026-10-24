from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "shop_automation_platform",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.campaign_tasks", "app.tasks.social_tasks", "app.tasks.automation_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
