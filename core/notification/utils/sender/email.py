from notification.utils.dataclass import UserDelivery
from notification.utils.sender.abc import SenderABC
from django.core.mail import EmailMessage
from django.conf import settings


class EmailSender(SenderABC):
    """Посылает email уведомление."""

    def _send(self, subject: str, message: str, contacts: list[str]) -> list[str]:
        """Посылает уведомление через сторонний сервис"""
        email_msg = EmailMessage(
            subject=subject,
            body=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            bcc=contacts,
        )
        if email_msg.send():
            return contacts

    def set_status(
        self, sucsess: list[str], users: list[UserDelivery]
    ) -> list[UserDelivery]:
        """Получает список успешно отправленных контактов и изменяет состояние уведомления в данных"""
        for user in users:
            if user.contact.email in sucsess:
                user.delivered = True
        return users

    def _get_contact(self, users: list[UserDelivery]) -> list[str]:
        """Извлекает из данных контакты"""

        return [user.contact.email for user in users if user.contact.email]
