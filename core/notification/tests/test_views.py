# notification/tests/test_views.py
import json
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from notification.models import MassNotification, NotificationRecipient
from notification.serializers import MassNotificationCreateSerializer
from rest_framework import serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .factories import UserFactory

User = get_user_model()


@pytest.mark.django_db
class TestNotificationView:

    def setup_method(self):
        """Устанавливает APIClient и аутентифицирует пользователя перед каждым тестом."""
        self.client = APIClient()
        self.user = UserFactory()
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.token.key)

    def test_post_success_with_immediate_send(self, mocker):
        """Тест успешного создания рассылки с немедленной отправкой."""

        mock_task = mocker.patch("notification.views.notification_immediately")

        user_to_notify = UserFactory()
        payload = {
            "subject": "Тестовая рассылка",
            "message": "Содержание тестовой рассылки.",
            "user_id": [user_to_notify.id],
            "immediately": True,
            "priority_order": ["email", "telegram"],
        }

        url = reverse("Notification API")
        response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_204_NO_CONTENT

        notification = MassNotification.objects.get(subject="Тестовая рассылка")
        assert notification.message == "Содержание тестовой рассылки."
        assert notification.created_by == self.user
        assert notification.immediately is True
        assert notification.status == MassNotification.Status.PENDING
        assert notification.priority_order == ["email", "telegram"]
        assert NotificationRecipient.objects.filter(
            notification=notification, user=user_to_notify
        ).exists()
        mock_task.delay_on_commit.assert_called_once_with(notification.id)

    def test_post_success_without_immediate_send(self, mocker):
        """Тест успешного создания рассылки без немедленной отправки."""

        mock_task = mocker.patch("notification.views.notification_immediately")
        user_to_notify = UserFactory()
        payload = {
            "subject": "Тестовая рассылка без отправки",
            "message": "Содержание тестовой рассылки.",
            "user_id": [user_to_notify.id],
            "immediately": False,
            "priority_order": ["sms"],
        }

        url = reverse("Notification API")
        response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_204_NO_CONTENT

        notification = MassNotification.objects.get(
            subject="Тестовая рассылка без отправки"
        )
        assert notification.message == "Содержание тестовой рассылки."
        assert notification.created_by == self.user
        assert notification.immediately is False
        mock_task.delay_on_commit.assert_not_called()

    def test_post_invalid_data_returns_400(self, mocker):
        """Тест возврата 400 при невалидных данных(subject отсутствует)."""

        mocker.patch("notification.views.notification_immediately")

        payload = {"message": "Сообщение без темы.", "user_id": [self.user.id]}

        url = reverse("Notification API")
        response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "subject" in response.data
        assert MassNotification.objects.count() == 0

    def test_post_unauthorized_without_token(self):
        """Тест возврата 401 при отсутствии токена(сбрасываем credentials)."""

        self.client.credentials()

        payload = {
            "subject": "Тестовая рассылка",
            "message": "Сообщение.",
            "user_id": [self.user.id],
        }

        url = reverse("Notification API")
        response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_post_unauthorized_with_invalid_token(self):
        """Тест возврата 401 при невалидном токене."""

        self.client.credentials(HTTP_AUTHORIZATION="Token invalidtoken12345")

        payload = {
            "subject": "Тестовая рассылка",
            "message": "Сообщение.",
            "user_id": [self.user.id],
        }
        url = reverse("Notification API")
        response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_post_validation_error_returns_400(self, mocker):
        """Тест возврата 400 при ValidationError в сериализаторе."""

        mocker.patch("notification.views.notification_immediately")

        payload = {
            "subject": "Тестовая рассылка",
            "message": "Сообщение.",
            "user_id": [self.user.id],
        }

        url = reverse("Notification API")

        with patch.object(
            MassNotificationCreateSerializer,
            "save",
            side_effect=serializers.ValidationError("Test validation error"),
        ):
            response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data == {"error": "Validation error"}

    def test_post_internal_error_returns_500(self, mocker):
        """Тест возврата 500 при внутренней ошибке."""

        mocker.patch("notification.views.notification_immediately")

        payload = {
            "subject": "Тестовая рассылка",
            "message": "Сообщение.",
            "user_id": [self.user.id],
        }

        url = reverse("Notification API")

        with patch.object(
            MassNotification,
            "save",
            side_effect=Exception("Database connection failed"),
        ):
            response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data == {"error": "Internal server error"}

    def test_post_with_multiple_users(self, mocker):
        """Тест создания рассылки с несколькими пользователями."""

        users_to_notify = UserFactory.create_batch(3)
        user_ids = [u.id for u in users_to_notify]

        payload = {
            "subject": "Рассылка нескольким",
            "message": "Привет, группа!",
            "user_id": user_ids,
            "immediately": False,
        }

        url = reverse("Notification API")
        response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_204_NO_CONTENT

        notification = MassNotification.objects.get(subject="Рассылка нескольким")
        assert (
            NotificationRecipient.objects.filter(notification=notification).count() == 3
        )
        for user in users_to_notify:
            assert NotificationRecipient.objects.filter(
                notification=notification, user=user
            ).exists()
