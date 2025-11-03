from abc import ABC, abstractmethod
from notification.utils.dataclass import UserDelivery


class SenderABC(ABC):
    def send_notification(
        self, subject: str, message: str, users: list[UserDelivery]
    ) -> list[UserDelivery]:
        """Основной метод отправки уведомлений"""

        sucsess: list[str] = self._send(
            subject=subject, message=message, contacts=self._get_contact(users=users)
        )
        return self.set_status(sucsess=sucsess, users=users)

    @abstractmethod
    def _send(self, subject: str, message: str, contacts: list[str]) -> list[str]:
        """Посылает уведомление через сторонний сервис"""

    @abstractmethod
    def set_status(
        self, sucsess: list[str], users: list[UserDelivery]
    ) -> list[UserDelivery]:
        """Получает список успешно отправленных контактов и изменяет состояние уведомления в данных"""

    @abstractmethod
    def _get_contact(self, users: list[UserDelivery]) -> list[str]:
        """Извлекает из данных контакты"""
