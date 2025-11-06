import asyncio
from celery import shared_task
from .utils.sender.telegram import TelegramSender
from .utils.notifications import NotificationManager
from django.contrib.auth import get_user_model

User = get_user_model()


@shared_task(name="telegran_contacts_search")
def telegran_contacts_search() -> None:
    """Обновляет в кэше ID контактов telegrsm"""

    asyncio.run(TelegramSender().search_telegram_user_id())


@shared_task(name="notification_check")
def notification_check() -> None:
    """Периодическая проверка отправки уведомлений."""

    NotificationManager().send()


@shared_task(name="notification_immediately")
def notification_immediately(id: int) -> None:
    """Немедленный запуск рассылки."""

    NotificationManager(id=id).send()
