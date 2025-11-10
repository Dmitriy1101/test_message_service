import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from django.core.cache import cache
from django.test import override_settings
from notification.utils.dataclass import UserContact, UserDelivery
from notification.utils.sender.telegram import TelegramSender
from telegram import Update, User
from telegram.error import TelegramError


class TestTelegramSender:

    def setup_method(self):
        """Очистка кэша перед каждым тестом."""
        cache.clear()

    def test_send_calls_bot_message_and_returns_result(self, mocker):
        """Тест метода _send: вызывает _bot_message и возвращает результат."""

        sender = TelegramSender()
        mock_bot_message = mocker.patch.object(
            sender, "_bot_message", return_value=["user1", "user2"]
        )
        subject = "Тестовая тема"
        message = "Текст сообщения"
        contacts = ["@user1", "@user2"]

        result = sender._send(subject, message, contacts)

        expected_msg = f"{subject}\n\n{message}"
        mock_bot_message.assert_called_once_with(
            message=expected_msg, contacts=contacts
        )
        assert result == ["user1", "user2"]

    def test_set_status_updates_delivered_flag(self):
        """Тест метода set_status: обновляет флаг delivered."""

        contact1 = UserContact(
            email="test1@example.com", telegramm="@user1", phone=None
        )
        contact2 = UserContact(
            email="test2@example.com", telegramm="@user2", phone=None
        )
        contact3 = UserContact(
            email="test3@example.com", telegramm="@user3", phone=None
        )

        user1 = UserDelivery(id=1, contact=contact1, delivered=False)
        user2 = UserDelivery(id=2, contact=contact2, delivered=False)
        user3 = UserDelivery(id=3, contact=contact3, delivered=False)

        users = [user1, user2, user3]
        successful_contacts = ["@user1", "@user3"]

        sender = TelegramSender()
        updated_users = sender.set_status(sucsess=successful_contacts, users=users)

        assert updated_users[0].delivered is True
        assert updated_users[1].delivered is False
        assert updated_users[2].delivered is True

    def test_get_contact_filters_and_returns_telegram_contacts(self):
        """Тест метода _get_contact: извлекает контакты."""

        contact_with_telegram = UserContact(
            email="test1@example.com", telegramm="@user1", phone=None
        )
        contact_without_telegram = UserContact(
            email="test2@example.com", telegramm=None, phone=None
        )
        contact_with_telegram2 = UserContact(
            email="test3@example.com", telegramm="@user3", phone=None
        )

        user1 = UserDelivery(id=1, contact=contact_with_telegram, delivered=False)
        user2 = UserDelivery(id=2, contact=contact_without_telegram, delivered=False)
        user3 = UserDelivery(id=3, contact=contact_with_telegram2, delivered=False)

        users = [user1, user2, user3]

        sender = TelegramSender()
        contacts = sender._get_contact(users)

        assert contacts == ["@user1", "@user3"]

    def test_bot_message_success_with_cache_hit(self, mocker):
        """Тест _bot_message: успешная отправка с данными из кэша."""

        message_text = "Тестовое сообщение"
        contacts = ["@user1", "https://t.me/user2  "]
        cached_data = {"user1": "123", "user2": "456"}

        sender = TelegramSender()

        mock_get_cache = mocker.patch.object(
            sender, "get_cache_bot_contacts", return_value=cached_data
        )
        mock_set_cache = mocker.patch.object(sender, "set_cache_bot_contacts")

        mock_bot_instance = AsyncMock()
        mock_bot_instance.send_message = AsyncMock()

        with patch.object(
            TelegramSender, "bot", new_callable=lambda: mock_bot_instance
        ):
            result = asyncio.run(
                sender._bot_message(message=message_text, contacts=contacts)
            )

        mock_get_cache.assert_called_once()
        mock_set_cache.assert_not_called()
        expected_calls = [
            mocker.call(chat_id="123", text=message_text),
            mocker.call(chat_id="456", text=message_text),
        ]
        mock_bot_instance.send_message.assert_has_awaits(expected_calls)
        assert set(result) == set(["@user1", "https://t.me/user2  "])

    def test_bot_message_success_with_cache_miss_and_search(self, mocker):
        """
        Тест _bot_message: успешная отправка, если кэш пуст, вызывает search_telegram_user_id.
        Проверяет, что search_telegram_user_id вызывается и возвращает данные,
        и что send_message вызывается с этими данными.
        Проверка вызова set_cache_bot_contacts внутри search_telegram_user_id вынесена в отдельный тест.
        """

        message_text = "Тестовое сообщение"
        contacts = ["@user1"]
        cached_data_before_search = {}
        search_result = {"user1": "123"}
        expected_user_id = "123"

        sender = TelegramSender()
        mock_get_cache = mocker.patch.object(
            sender, "get_cache_bot_contacts", return_value=cached_data_before_search
        )
        mock_search = mocker.patch.object(
            sender, "search_telegram_user_id", return_value=search_result
        )
        mock_bot_instance = AsyncMock()
        mock_bot_instance.send_message = AsyncMock()

        with patch.object(
            TelegramSender, "bot", new_callable=lambda: mock_bot_instance
        ):
            result = asyncio.run(
                sender._bot_message(message=message_text, contacts=contacts)
            )

        mock_get_cache.assert_called_once()
        mock_search.assert_called_once()
        mock_bot_instance.send_message.assert_awaited_once_with(
            chat_id=expected_user_id, text=message_text
        )
        assert result == contacts

    def test_bot_message_failure_with_error(self, mocker):
        """Тест _bot_message: обработка ошибки TelegramError."""
        message_text = "Тестовое сообщение"
        contacts = ["@user1"]
        cached_data = {"user1": "123"}

        sender = TelegramSender()

        mock_get_cache = mocker.patch.object(
            sender, "get_cache_bot_contacts", return_value=cached_data
        )

        mock_bot_instance = AsyncMock()
        mock_bot_instance.send_message = AsyncMock(
            side_effect=TelegramError("Test error")
        )
        with patch.object(
            TelegramSender, "bot", new_callable=lambda: mock_bot_instance
        ):
            with pytest.raises(TelegramError, match="Test error"):
                asyncio.run(
                    sender._bot_message(message=message_text, contacts=contacts)
                )

        mock_get_cache.assert_called_once()
        mock_bot_instance.send_message.assert_awaited_once_with(
            chat_id="123", text=message_text
        )

    def test_bot_message_failure_no_contacts_found(self, mocker):
        """Тест _bot_message: возврат None, если контакты не найдены в кэше."""

        message_text = "Тестовое сообщение"
        contacts = ["@unknown_user"]
        cached_data = {"user1": "123"}

        sender = TelegramSender()

        mock_get_cache = mocker.patch.object(
            sender, "get_cache_bot_contacts", return_value=cached_data
        )

        mock_bot_instance = AsyncMock()
        mock_bot_instance.send_message = AsyncMock()
        with patch.object(
            TelegramSender, "bot", new_callable=lambda: mock_bot_instance
        ):
            result = asyncio.run(
                sender._bot_message(message=message_text, contacts=contacts)
            )

        mock_get_cache.assert_called_once()
        mock_bot_instance.send_message.assert_not_called()
        assert result == None

    def test_search_telegram_user_id(self, mocker):
        """
        Тест search_telegram_user_id: извлечение данных из обновлений и сохранение в кэш.
        Проверяет, что код корректно обрабатывает случаи, когда
        u.my_chat_member.new_chat_member существует как атрибут, но равен None.
        """

        user1 = User(id=111, first_name="User1", username="user1", is_bot=False)
        user2 = User(id=222, first_name="User2", username="user2", is_bot=False)

        update1 = MagicMock(spec=Update)
        update1.my_chat_member = MagicMock()
        update1.my_chat_member.from_user = user1
        update1.my_chat_member.new_chat_member = None
        update2 = MagicMock(spec=Update)
        update2.my_chat_member = MagicMock()
        update2.my_chat_member.from_user = user1
        new_member_mock = MagicMock()
        new_member_mock.user = user2

        update2.my_chat_member.new_chat_member = new_member_mock

        updates = [update1, update2]

        sender = TelegramSender()

        mock_bot_instance = AsyncMock()
        mock_bot_instance.get_updates = AsyncMock(return_value=updates)
        mock_get_cache_in_search = mocker.patch.object(
            sender, "get_cache_bot_contacts", return_value={}
        )
        mock_set_cache = mocker.patch.object(sender, "set_cache_bot_contacts")

        with patch.object(
            TelegramSender, "bot", new_callable=lambda: mock_bot_instance
        ):
            result = asyncio.run(sender.search_telegram_user_id())

        mock_bot_instance.get_updates.assert_awaited_once()
        mock_get_cache_in_search.assert_called_once()
        expected_data = {"user1": "111", "user2": "222"}
        mock_set_cache.assert_called_once_with(value=expected_data)
        assert result == expected_data

    def test_get_cache_bot_contacts_empty(self):
        """Тест get_cache_bot_contacts: возврат пустого словаря, если кэш пуст."""

        sender = TelegramSender()
        key = sender.chache_key

        cache.delete(key)

        result = sender.get_cache_bot_contacts()

        assert result == {}

    def test_get_cache_bot_contacts_with_data(self):
        """Тест get_cache_bot_contacts: возврат десериализованных данных."""

        sender = TelegramSender()
        key = sender.chache_key
        data_to_cache = {"user1": "123", "user2": "456"}
        serialized_data = json.dumps(data_to_cache)

        cache.set(key, serialized_data)

        result = sender.get_cache_bot_contacts()

        assert result == data_to_cache

    def test_set_cache_bot_contacts_success(self):
        """Тест set_cache_bot_contacts: сохранение данных в кэш."""

        sender = TelegramSender()
        key = sender.chache_key
        data_to_set = {"user1": "123", "user2": "456"}

        sender.set_cache_bot_contacts(data_to_set)

        cached_value = cache.get(key)
        assert json.loads(cached_value) == data_to_set

    def test_set_cache_bot_contacts_type_error(self):
        """Тест set_cache_bot_contacts: проверка типа данных."""

        sender = TelegramSender()

        with pytest.raises(TypeError, match="Bot contacts only dict structure."):
            sender.set_cache_bot_contacts("not_a_dict")

    def test_bot_property_initializes_once(self, mocker):
        """Тест свойства bot: инициализация выполняется только один раз."""

        mock_bot_class = mocker.patch("notification.utils.sender.telegram.Bot")
        fake_token = "fake_token_123"
        with override_settings(TELEGRAM_BOT_TOKEN=fake_token):
            sender = TelegramSender()

            bot1 = sender.bot
            bot2 = sender.bot
            mock_bot_class.assert_called_once_with(fake_token)
            assert bot1 is bot2

    def test_chache_key_returns_constant(self):
        """Тест свойства chache_key: возврат константы."""

        sender = TelegramSender()
        assert sender.chache_key == "TELEGRAM_CONTACTS_CACHE_KEY"
