# notification/tests/test_serializers.py
import pytest
from django.contrib.auth import get_user_model
from notification.models import NotificationRecipient
from notification.serializers import MassNotificationCreateSerializer
from rest_framework import serializers

from .factories import UserFactory

User = get_user_model()


@pytest.mark.django_db
class TestMassNotificationCreateSerializer:

    def test_is_valid_with_valid_data(self):
        """Тест валидации с корректными данными."""

        user1 = UserFactory()
        user2 = UserFactory()
        valid_data = {
            "subject": "Тестовая рассылка",
            "message": "Содержание сообщения.",
            "user_id": [user1.id, user2.id],
            "immediately": True,
            "priority_order": ["telegram", "email"],
        }

        serializer = MassNotificationCreateSerializer(data=valid_data)
        assert serializer.is_valid(), f"Сериализатор не валиден: {serializer.errors}"
        assert serializer.validated_data["subject"] == "Тестовая рассылка"
        assert serializer.validated_data["message"] == "Содержание сообщения."
        assert list(serializer.validated_data["users"]) == [user1, user2]
        assert serializer.validated_data["immediately"] is True
        assert serializer.validated_data["priority_order"] == ["telegram", "email"]

    def test_create_creates_notification_and_recipients(self):
        """Тест метода create: создание рассылки и получателей."""

        user1 = UserFactory()
        user2 = UserFactory()
        valid_data = {
            "subject": "Тест создания",
            "message": "Сообщение для создания.",
            "user_id": [user1.id, user2.id],
            "immediately": False,
            "priority_order": ["sms", "email"],
        }

        serializer = MassNotificationCreateSerializer(data=valid_data)
        assert serializer.is_valid()

        created_notification = serializer.save(created_by=UserFactory())

        assert created_notification.subject == "Тест создания"
        assert created_notification.message == "Сообщение для создания."
        assert created_notification.immediately is False
        assert created_notification.priority_order == ["sms", "email"]
        assert created_notification.total_recipients == 2

        assert (
            NotificationRecipient.objects.filter(
                notification=created_notification
            ).count()
            == 2
        )
        assert NotificationRecipient.objects.filter(
            notification=created_notification, user=user1
        ).exists()
        assert NotificationRecipient.objects.filter(
            notification=created_notification, user=user2
        ).exists()

    def test_validate_priority_order_success(self):
        """Тест валидации priority_order с валидными и уникальными каналами."""

        serializer = MassNotificationCreateSerializer()
        valid_order = ["email", "telegram", "sms"]
        validated_order = serializer.validate_priority_order(valid_order)
        assert validated_order == valid_order

    def test_validate_priority_order_duplicate_channels(self):
        """Тест валидации priority_order с дубликатами."""

        serializer = MassNotificationCreateSerializer()
        invalid_order_with_duplicates = ["email", "telegram", "email"]
        with pytest.raises(serializers.ValidationError) as exc_info:
            serializer.validate_priority_order(invalid_order_with_duplicates)
        assert "Порядок приоритета должен содержать уникальные значения." in str(
            exc_info.value
        )

    def test_validate_priority_order_invalid_channels(self):
        """Тест валидации priority_order с невалидными каналами."""

        serializer = MassNotificationCreateSerializer()
        invalid_order_with_wrong_channel = ["email", "invalid_channel", "sms"]
        with pytest.raises(serializers.ValidationError) as exc_info:
            serializer.validate_priority_order(invalid_order_with_wrong_channel)
        error_message = str(exc_info.value)
        assert "invalid_channel" in error_message
        assert "email" in error_message
        assert "sms" in error_message

    def test_validate_priority_order_mixed_invalid_and_valid(self):
        """Тест валидации priority_order с комбинацией валидных и невалидных каналов."""

        serializer = MassNotificationCreateSerializer()
        mixed_order = ["email", "invalid1", "telegram", "invalid2", "sms"]
        with pytest.raises(serializers.ValidationError) as exc_info:
            serializer.validate_priority_order(mixed_order)
        error_message = str(exc_info.value)
        assert "invalid1" in error_message
        assert "invalid2" in error_message
        assert "email" in error_message
        assert "telegram" in error_message
        assert "sms" in error_message

    def test_validate_empty_user_ids(self):
        """Тест валидации с пустым списком user_id."""

        serializer = MassNotificationCreateSerializer(
            data={"subject": "Тест", "message": "Сообщение", "user_id": []}
        )

        assert not serializer.is_valid()
        assert "user_ids is empty/" in str(serializer.errors)

    def test_validate_non_existing_user_ids(self):
        """Тест валидации с несуществующими ID пользователей."""

        existing_user = UserFactory()
        serializer = MassNotificationCreateSerializer(
            data={
                "subject": "Тест",
                "message": "Сообщение",
                "user_id": [existing_user.id, 999999, 888888],
            }
        )

        assert not serializer.is_valid()
        error_message = str(serializer.errors)
        assert "999999" in error_message
        assert "888888" in error_message
        assert "not found" in error_message

    def test_validate_mixed_existing_and_non_existing_user_ids(self):
        """Тест валидации со смешанным списком существующих и несуществующих ID."""

        existing_user1 = UserFactory()
        existing_user2 = UserFactory()

        serializer = MassNotificationCreateSerializer(
            data={
                "subject": "Тест",
                "message": "Сообщение",
                "user_id": [existing_user1.id, 999999, existing_user2.id, 888888],
            }
        )
        assert not serializer.is_valid()
        error_message = str(serializer.errors)
        assert "999999" in error_message
        assert "888888" in error_message
        assert "not found" in error_message

    def test_validate_success_with_existing_user_ids(self):
        """Тест валидации с корректным списком существующих ID пользователей."""

        user1 = UserFactory()
        user2 = UserFactory()
        user3 = UserFactory()
        serializer = MassNotificationCreateSerializer(
            data={
                "subject": "Тест",
                "message": "Сообщение",
                "user_id": [user1.id, user2.id, user3.id],
            }
        )
        assert serializer.is_valid()
        assert set(serializer.validated_data["users"]) == {user1, user2, user3}

    def test_create_links_correct_users(self):
        """Тест, что create связывает рассылку с правильными пользователями."""

        user_to_notify1 = UserFactory()
        user_to_notify2 = UserFactory()
        user_to_notify3 = UserFactory()
        valid_data = {
            "subject": "Тест связей",
            "message": "Сообщение.",
            "user_id": [user_to_notify1.id, user_to_notify2.id, user_to_notify3.id],
            "immediately": False,
        }

        serializer = MassNotificationCreateSerializer(data=valid_data)
        assert serializer.is_valid()

        created_notification = serializer.save(created_by=UserFactory())
        created_recipients = NotificationRecipient.objects.filter(
            notification=created_notification
        ).values_list("user", flat=True)
        expected_user_ids = {user_to_notify1.id, user_to_notify2.id, user_to_notify3.id}

        assert set(created_recipients) == expected_user_ids
        assert created_notification.total_recipients == 3

    def test_defaults_applied(self):
        """Тест, что значения по умолчанию применяются корректно."""

        user = UserFactory()
        data_without_defaults = {
            "subject": "Тест умолчаний",
            "message": "Сообщение.",
            "user_id": [user.id],
        }

        serializer = MassNotificationCreateSerializer(data=data_without_defaults)
        assert serializer.is_valid()

        validated_data = serializer.validated_data
        assert validated_data.get("immediately") is False
        assert validated_data.get("priority_order") == [
            "email",
            "telegram",
            "sms",
        ]
