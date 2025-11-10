import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from notification.models import MassNotification, NotificationRecipient

from .factories import (
    MassNotificationFactory,
    NotificationRecipientFactory,
    UserFactory,
)

User = get_user_model()


@pytest.mark.django_db
class TestMassNotificationModel:

    def test_str_representation(self):
        """Тест строкового представления модели MassNotification."""

        notification = MassNotificationFactory(subject="Приветствие")
        expected_str = "Рассылка #1: Приветствие"
        assert str(notification) == expected_str

    def test_default_status(self):
        """Тест статуса по умолчанию."""

        notification = MassNotificationFactory.build()
        assert notification.status == MassNotification.Status.PENDING

    def test_default_priority_order(self):
        """Тест порядка приоритета по умолчанию."""

        notification = MassNotificationFactory.build()
        assert notification.priority_order == ["email", "telegram", "sms"]

    def test_status_choices(self):
        """Тест доступных значений статуса."""

        choices = [choice[0] for choice in MassNotification.Status.choices]
        expected_choices = ["pending", "processing", "completed", "failed", "cancelled"]
        assert sorted(choices) == sorted(expected_choices)

    def test_unique_together_index_on_status_and_scheduled_for(self):
        """Тест индекса на статус и запланированное время."""

        notification = MassNotificationFactory(
            status=MassNotification.Status.PENDING, scheduled_for=timezone.now()
        )
        assert notification.status == MassNotification.Status.PENDING

    def test_created_at_auto_now_add(self):
        """Тест автоматического заполнения created_at."""

        before_save = timezone.now()
        notification = MassNotificationFactory()
        after_save = timezone.now()

        assert notification.created_at is not None
        assert before_save <= notification.created_at <= after_save

    def test_save_updates_total_recipients(self):
        """--------Тест, что save обновляет total_recipients."""

        notification = MassNotificationFactory()
        assert notification.total_recipients == 0

        user1 = UserFactory()
        user2 = UserFactory()
        notification.users.add(user1, user2)

        notification.refresh_from_db()
        assert notification.total_recipients == 0

        user3 = UserFactory()
        user4 = UserFactory()
        new_notification = MassNotificationFactory()
        NotificationRecipientFactory(notification=new_notification, user=user3)
        NotificationRecipientFactory(notification=new_notification, user=user4)

        assert new_notification.users.count() == 2

        new_notification.save()
        new_notification.refresh_from_db()
        assert new_notification.total_recipients == 2


@pytest.mark.django_db
class TestNotificationRecipientModel:

    def test_str_representation(self):
        """Тест строкового представления модели NotificationRecipient."""

        recipient = NotificationRecipientFactory()
        expected_str = (
            f"Получатель {recipient.user.id} для рассылки #{recipient.notification.id}"
        )
        assert str(recipient) == expected_str

    def test_delivery_status_choices(self):
        """Тест доступных значений статуса доставки."""

        choices = [choice[0] for choice in NotificationRecipient.DeliveryStatus.choices]
        expected_choices = ["pending", "sent", "failed", "no_channels"]
        assert sorted(choices) == sorted(expected_choices)

    def test_unique_together_constraint(self):
        """Тест ограничения уникальности notification + user."""

        notification = MassNotificationFactory()
        user = UserFactory()
        NotificationRecipientFactory(notification=notification, user=user)
        with pytest.raises(IntegrityError):
            NotificationRecipientFactory(notification=notification, user=user)

    def test_default_delivery_status(self):
        """Тест статуса доставки по умолчанию."""

        recipient = NotificationRecipientFactory.build()
        assert recipient.delivery_status == NotificationRecipient.DeliveryStatus.PENDING

    def test_cascade_delete_notification(self):
        """Тест каскадного удаления при удалении MassNotification."""

        notification = MassNotificationFactory()
        user = UserFactory()
        recipient = NotificationRecipientFactory(notification=notification, user=user)

        notification.delete()

        with pytest.raises(NotificationRecipient.DoesNotExist):
            recipient.refresh_from_db()

    def test_cascade_delete_user(self):
        """Тест каскадного удаления при удалении User."""

        notification = MassNotificationFactory()
        user = UserFactory()
        recipient = NotificationRecipientFactory(notification=notification, user=user)

        user.delete()

        with pytest.raises(NotificationRecipient.DoesNotExist):
            recipient.refresh_from_db()

    def test_delivered_via_choices(self):
        """Тест доступных значений канала доставки."""

        user = UserFactory()
        notification = MassNotificationFactory()
        recipient = NotificationRecipientFactory.build(
            user=user, notification=notification, delivered_via="email"
        )
        recipient.full_clean()
        assert recipient.delivered_via == "email"

        recipient_invalid = NotificationRecipientFactory.build(
            delivered_via="invalid_channel"
        )
        with pytest.raises(ValidationError):
            recipient_invalid.full_clean()

    def test_blank_error_message(self):
        """Тест, что error_message может быть пустым."""

        recipient = NotificationRecipientFactory(error_message="")
        assert recipient.error_message == ""

    def test_blank_sent_at(self):
        """Тест, что sent_at может быть пустым."""

        recipient = NotificationRecipientFactory(sent_at=None)
        assert recipient.sent_at is None

    def test_blank_scheduled_for_on_notification(self):
        """Тест, что scheduled_for может быть пустым."""

        notification = MassNotificationFactory(scheduled_for=None)
        assert notification.scheduled_for is None

    def test_default_counts_on_notification(self):
        """Тест значений по умолчанию для счётчиков."""

        notification = MassNotificationFactory.build()
        assert notification.total_recipients == 0
        assert notification.sent_count == 0
        assert notification.failed_count == 0

    def test_blank_started_at_completed_at_on_notification(self):
        """Тест, что started_at и completed_at могут быть пустыми."""

        notification = MassNotificationFactory(started_at=None, completed_at=None)
        assert notification.started_at is None
        assert notification.completed_at is None

    def test_related_name_access(self):
        """Тест доступа к получателям через related_name у MassNotification."""

        notification = MassNotificationFactory()
        user = UserFactory()
        recipient = NotificationRecipientFactory(notification=notification, user=user)

        assert recipient in notification.recipients.all()
        assert notification.recipients.count() == 1

    def test_related_name_access_user(self):
        """Тест доступа к получателям через related_name у User."""

        notification = MassNotificationFactory()
        user = UserFactory()
        recipient = NotificationRecipientFactory(notification=notification, user=user)

        assert recipient in user.notification_recipients.all()
        assert user.notification_recipients.count() == 1

    def test_related_name_access_notification_from_user(self):
        """Тест доступа к рассылкам через related_name у User."""

        notification = MassNotificationFactory()
        user = UserFactory()
        recipient = NotificationRecipientFactory(notification=notification, user=user)

        assert notification in user.mass_notifications.all()
        assert user.mass_notifications.count() == 1
