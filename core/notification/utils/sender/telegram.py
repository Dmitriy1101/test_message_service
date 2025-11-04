from notification.utils.dataclass import UserDelivery
from notification.utils.sender.abc import SenderABC
from telegram import Bot
from telegram.error import TelegramError
from django.conf import settings
import asyncio


class TelegramSender(SenderABC):
    """Отправить уведомление xерез telegrsm"""

    def _send(self, subject: str, message: str, contacts: list[str]) -> list[str]:
        """Посылает уведомление через сторонний сервис"""

        bot = Bot(settings.TELEGRAM_BOT_TOKEN)
        successful = []
        err: TelegramError = None
        for user in contacts:
            try:
                username = user.replace("https://t.me/", "").replace("@", "")
                asyncio.run(bot.send_message(chat_id=f"@{username}", text=message))
                successful.append(user)
            except TelegramError as e:
                err = e
        if successful:
            return successful
        elif err:
            raise err

    def set_status(
        self, sucsess: list[str], users: list[UserDelivery]
    ) -> list[UserDelivery]:
        """Получает список успешно отправленных контактов и изменяет состояние уведомления в данных"""
        for user in users:
            if user.contact.telegramm in sucsess:
                user.delivered = True
        return users

    def _get_contact(self, users: list[UserDelivery]) -> list[str]:
        """Извлекает из данных контакты"""

        return [user.contact.telegramm for user in users if user.contact.telegramm]
