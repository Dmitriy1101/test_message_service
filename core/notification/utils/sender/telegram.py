import asyncio
import json
from typing import Literal

from django.conf import settings
from django.core.cache import cache
from notification.utils.dataclass import UserDelivery
from notification.utils.sender.abc import SenderABC
from telegram import Bot, User
from telegram.error import TelegramError


class TelegramSender(SenderABC):
    """
    Реализация отправителя уведомлений через Telegram Bot API.

    Класс предоставляет функционал для массовой отправки сообщений пользователям
    Telegram через официального бота. Использует асинхронные методы для взаимодействия
    с Telegram API и кэширование для оптимизации поиска идентификаторов пользователей.

    Особенности:
    - Автоматическое разрешение username в user_id через кэш
    - Обработка обновлений бота для сбора контактов
    - Асинхронная отправка сообщений
    - Интеграция с Django caching framework

    Атрибуты:
        bot (Bot): Экземпляр Telegram Bot с настроенным токеном
        chache_key (str): Ключ для хранения кэшированных контактов

    Пример использования:
        ```python
        sender = TelegramSender()
        users = [UserDelivery(...), ...]
        result_users = sender.send(
            subject="Важное уведомление",
            message="Текст сообщения",
            users=users
        )
        ```

    Требования:
        - Настройка TELEGRAM_BOT_TOKEN в settings.py
        - Работающий Telegram Bot с разрешением на чтение сообщений
        - Общая группа, для общих контактов бота и пользователей
    """

    def _send(self, subject: str, message: str, contacts: list[str]) -> list[str]:
        """
        Основной метод отправки уведомлений через Telegram.

        Форматирует сообщение и асинхронно отправляет его списку контактов.
        Возвращает список успешно отправленных контактов.

        Args:
            subject (str): Заголовок уведомления
            message (str): Текст сообщения для отправки
            contacts (list[str]): Список контактов (username или URL) в Telegram

        Returns:
            list[str]: Список контактов, которым сообщение было успешно доставлено

        Raises:
            TelegramError: Если возникла ошибка при отправке и ни одно сообщение не отправлено
        """

        msg: str = f"{subject}\n\n{message}"

        return asyncio.run(self._bot_message(message=msg, contacts=contacts))

    def set_status(
        self, sucsess: list[str], users: list[UserDelivery]
    ) -> list[UserDelivery]:
        """
        Обновляет статус доставки для пользователей на основе результатов отправки.

        Проходит по списку пользователей и отмечает как доставленные те,
        чьи Telegram-контакты присутствуют в списке успешных отправок.

        Args:
            sucsess (list[str]): Список успешно отправленных контактов
            users (list[UserDelivery]): Список пользователей для обновления статуса

        Returns:
            list[UserDelivery]: Обновленный список пользователей с актуальными статусами доставки
        """

        for user in users:
            if user.contact.telegramm in sucsess:
                user.delivered = True
        return users

    def _get_contact(self, users: list[UserDelivery]) -> list[str]:
        """
        Извлекает Telegram-контакты из списка пользователей.

        Фильтрует пользователей, оставляя только тех, у кого указан Telegram-контакт,
        и возвращает список этих контактов.

        Args:
            users (list[UserDelivery]): Список пользователей с контактной информацией

        Returns:
            list[str]: Список Telegram-контактов (username) пользователей
        """

        return [user.contact.telegramm for user in users if user.contact.telegramm]

    async def _bot_message(self, message: str, contacts: list[str]) -> list[str] | None:
        """
        Асинхронно отправляет сообщение списку контактов через Telegram Bot.

        Процесс отправки:
        1. Получает кэшированные контакты или обновляет их через search_telegram_user_id()
        2. Для каждого контакта нормализует username и находит соответствующий user_id
        3. Отправляет сообщение через Bot API
        4. Собирает статистику успешных отправок

        Args:
            message (str): Текст сообщения для отправки
            contacts (list[str]): Список контактов для отправки

        Returns:
            list[str]: Список успешно отправленных контактов

        Raises:
            TelegramError: Последняя возникшая ошибка, если ни одно сообщение не отправлено
        """

        cache_contact: dict = self.get_cache_bot_contacts()
        if not cache_contact:
            cache_contact = await self.search_telegram_user_id()
        successful: list[str] = []
        err: TelegramError = None
        for user in contacts:
            username = user.replace("https://t.me/", "").replace("@", "")
            user_id: str | None = cache_contact.get(username)
            if not user_id:
                continue
            try:
                await self.bot.send_message(chat_id=user_id, text=message)
                successful.append(user)
            except TelegramError as e:
                err = e
                continue
        if successful:
            return successful
        elif err:
            raise err

    async def search_telegram_user_id(self) -> dict:
        """
        Собирает информацию о пользователях бота через получение обновлений.

        Анализирует обновления бота (updates) для сбора соответствий
        между username и user_id пользователей, взаимодействовавших с ботом.

        Returns:
            dict: Словарь с соответствиями username -> user_id

        Note:
            Для работы метода бот должен иметь разрешение на чтение сообщений
        """

        updates = await self.bot.get_updates()
        data: dict = self.get_cache_bot_contacts()
        for u in updates:
            if u.my_chat_member:
                f_user: User = u.my_chat_member.from_user
                data[f_user.username] = str(f_user.id)
                if hasattr(u.my_chat_member, "new_chat_member") and (
                    not u.my_chat_member.new_chat_member.user.is_bot
                ):
                    n_user: User = u.my_chat_member.new_chat_member.user
                    data[n_user.username] = str(n_user.id)

        self.set_cache_bot_contacts(value=data)
        return data

    def get_cache_bot_contacts(self) -> dict:
        """
        Получает кэшированные контакты бота из системы кэширования Django.

        Returns:
            dict: Словарь с кэшированными контактами в формате {username: user_id}
                  или пустой словарь, если кэш пуст

        Note:
            Данные хранятся в сериализованном JSON формате
        """

        _ = cache.get(self.chache_key, {})
        if _:
            return json.loads(_)
        return {}

    def set_cache_bot_contacts(self, value: dict) -> None:
        """
        Сохраняет контакты бота в систему кэширования Django.

        Args:
            value (dict): Словарь с контактами для кэширования

        Raises:
            TypeError: Если переданное значение не является словарем
        """

        if not isinstance(value, dict):
            raise TypeError("Bot contacts only dict structure.")
        cache.set(self.chache_key, json.dumps(value))

    @property
    def bot(self) -> Bot:
        """
        Свойство для ленивой инициализации экземпляра Telegram Bot.

        Создает экземпляр бота только при первом обращении, используя
        токен из настроек Django (TELEGRAM_BOT_TOKEN).

        Returns:
            Bot: Экземпляр Telegram Bot с настроенным токеном

        Raises:
            ImproperlyConfigured: Если TELEGRAM_BOT_TOKEN не настроен
        """

        _ = "_bot"
        if not hasattr(self, _):
            bot = Bot(settings.TELEGRAM_BOT_TOKEN)
            setattr(self, _, bot)
        return getattr(self, _)

    @property
    def chache_key(self) -> Literal["TELEGRAM_CONTACTS_CACHE_KEY"]:
        """
        Ключ для хранения кэшированных контактов в системе кэширования.

        Returns:
            str: Константный ключ "TELEGRAM_CONTACTS_CACHE_KEY"
        """

        return "TELEGRAM_CONTACTS_CACHE_KEY"
