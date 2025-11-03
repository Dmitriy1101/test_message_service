from notification.utils.dataclass import UserDelivery
from notification.utils.sender.abc import SenderABC


class SmsSender(SenderABC):
    """Отправить уведомление xерез sms"""

    def _send(self, subject: str, message: str, contacts: list[str]) -> list[str]:
        """Посылает уведомление через сторонний сервис"""

        return contacts

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
