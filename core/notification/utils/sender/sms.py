from notification.utils.dataclass import UserDelivery
from notification.utils.sender.abc import SenderABC


class SMSServiceNotConfiguredError(Exception):
    """Ошибка конфигурации SMS сервиса"""

    def __init__(self):
        message = (
            "Данные сервиса для создания функционала sms рассылки не предоставлены."
        )
        super().__init__(message)


class SmsSender(SenderABC):
    """Отправить уведомление xерез sms"""

    def _send(self, subject: str, message: str, contacts: list[str]) -> list[str]:
        """Посылает уведомление через сторонний сервис"""

        raise SMSServiceNotConfiguredError

    def set_status(
        self, sucsess: list[str], users: list[UserDelivery]
    ) -> list[UserDelivery]:
        """Получает список успешно отправленных контактов и изменяет состояние уведомления в данных"""
        for user in users:
            if user.contact.phone in sucsess:
                user.delivered = True
        return users

    def _get_contact(self, users: list[UserDelivery]) -> list[str]:
        """Извлекает из данных контакты"""

        return [user.contact.phone for user in users if user.contact.phone]
