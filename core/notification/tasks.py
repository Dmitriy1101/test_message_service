import pprint
from celery import shared_task
from .models import MassNotification, NotificationRecipient
from django.db.models import QuerySet, Prefetch
from .utils.notifications import NotificationManager
from django.contrib.auth import get_user_model

User = get_user_model()


@shared_task(name="notification_check")
def notification_check() -> None:
    NotificationManager().send()


@shared_task(name="notification_immediately")
def notification_immediately(id: int) -> None:
    NotificationManager(id=id).send()
