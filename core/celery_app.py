"""
Настройка Celery.
"""

import os
import time
from datetime import datetime

from celery import Celery
from celery.schedules import crontab
from django.conf import settings
from logging import Logger, getLogger

log = getLogger(__name__)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")


app = Celery("core")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.conf.broker_url = settings.CELERY_BROKER_URL
app.autodiscover_tasks()


app.conf.beat_schedule = {
    "be-ready": {
        "task": "notification_check",
        "schedule": crontab(minute="*/10"),
    },
}
