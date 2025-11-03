"""
Протоколы (интерфейсы) для сервисов отправки уведомлений.

Определяет контракты, которые должны реализовывать все отправители уведомлений
для обеспечения совместимости в системе.

Protocols (interfaces) for notification sending services.

Defines contracts that all notification senders must implement
to ensure compatibility within the system.
"""

from typing import Protocol
from .dataclass import UserDelivery


class Sender(Protocol):
    """
    Протокол для сервисов отправки уведомлений.

    Определяет обязательный контракт, который должны реализовывать все
    классы-отправители для интеграции с системой уведомлений.

    Methods:
        send_notification: Основной метод отправки уведомлений
    """

    def send_notification(
        self, subject: str, message: str, users: list[UserDelivery]
    ) -> list[UserDelivery]:
        """
        Отправляет уведомление списку пользователей.

        Args:
            subject: Тема уведомления
            message: Текст сообщения
            users: Список пользователей для отправки

        Returns:
            list[UserDelivery]: Обновленный список пользователей со статусами доставки

        Note:
            Реализации должны обновлять поле `delivered` для каждого пользователя
            в зависимости от результата отправки
        """
