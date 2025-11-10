from datetime import timedelta
from unittest.mock import Mock, call, patch

import pytest
from django.db import transaction
from django.utils import timezone
from notification.models import MassNotification, NotificationRecipient
from notification.utils.dataclass import (
    NotificationRecipientUpdate,
    NotificationUsers,
    UserContact,
    UserDelivery,
)
from notification.utils.notifications import NotificationManager
from notification.utils.sender import EmailSender, SmsSender, TelegramSender
from users.models import UserContact as UserContactModel

from .factories import (
    MassNotificationFactory,
    NotificationRecipientFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestNotificationManager:

    def test_init_with_id(self):
        """Тест инициализации с ID."""

        manager = NotificationManager(id=123)
        assert manager.id == 123

    def test_init_without_id(self):
        """Тест инициализации без ID."""

        manager = NotificationManager()
        assert manager.id is None

    def test_get_pending_notification_with_id(self):
        """Тест получения рассылки по ID."""

        notification = MassNotificationFactory(status=MassNotification.Status.PENDING)

        user = UserFactory()
        NotificationRecipientFactory(
            notification=notification,
            user=user,
            delivery_status=NotificationRecipient.DeliveryStatus.PENDING,
        )

        manager = NotificationManager(id=notification.id)
        queryset = manager.get_pending_notification()

        assert queryset.count() == 1
        notification.refresh_from_db()
        assert notification.status == MassNotification.Status.PROCESSING
        assert notification.started_at is not None
        assert notification.immediately is False
        fetched_notification = queryset.first()
        assert hasattr(fetched_notification, "pending_recipients")

    def test_get_pending_notification_without_id(self):
        """Тест получения рассылок без ID (ожидающих и не немедленных)."""

        now = timezone.now()
        pending_notification = MassNotificationFactory(
            status=MassNotification.Status.PENDING,
            scheduled_for=None,
            immediately=False,
        )
        immediate_notification = MassNotificationFactory(
            status=MassNotification.Status.PENDING, scheduled_for=None, immediately=True
        )
        future_scheduled_notification = MassNotificationFactory(
            status=MassNotification.Status.PENDING,
            scheduled_for=now + timedelta(hours=1),
            immediately=False,
        )
        past_scheduled_immediate = MassNotificationFactory(
            status=MassNotification.Status.PENDING,
            scheduled_for=now - timedelta(hours=1),
            immediately=True,
        )

        processing_notification = MassNotificationFactory(
            status=MassNotification.Status.PROCESSING,
            scheduled_for=None,
            immediately=False,
        )
        user = UserFactory()
        NotificationRecipientFactory(
            notification=pending_notification,
            user=user,
            delivery_status=NotificationRecipient.DeliveryStatus.PENDING,
        )

        manager = NotificationManager()
        queryset = manager.get_pending_notification()

        assert queryset.count() == 1
        fetched_notification = queryset.first()
        assert fetched_notification.id == pending_notification.id
        pending_notification.refresh_from_db()
        immediate_notification.refresh_from_db()
        future_scheduled_notification.refresh_from_db()
        past_scheduled_immediate.refresh_from_db()
        processing_notification.refresh_from_db()

        assert pending_notification.status == MassNotification.Status.PROCESSING
        assert immediate_notification.status == MassNotification.Status.PENDING
        assert future_scheduled_notification.status == MassNotification.Status.PENDING
        assert past_scheduled_immediate.status == MassNotification.Status.PENDING
        assert processing_notification.status == MassNotification.Status.PROCESSING

    def test_get_pending_notification_none_found(self):
        """Тест получения рассылок, когда нет подходящих."""

        MassNotificationFactory(status=MassNotification.Status.PROCESSING)
        MassNotificationFactory(
            status=MassNotification.Status.PENDING, immediately=True
        )

        manager = NotificationManager()
        queryset = manager.get_pending_notification()

        assert queryset.count() == 0
        assert queryset.model == MassNotification

    def test_get_pending_notification_calls_select_for_update(self, mocker):
        """Тест, что get_pending_notification использует select_for_update."""

        mock_qs = mocker.patch(
            "notification.models.MassNotification.objects.select_for_update"
        )
        mock_filtered_qs = Mock()
        mock_qs.return_value = mock_filtered_qs
        mock_filtered_qs.filter.return_value = mock_filtered_qs
        mock_filtered_qs.exists.return_value = True
        mock_filtered_qs.values_list.return_value = [1]
        mock_filtered_qs.__len__ = Mock(return_value=1)

        manager = NotificationManager()
        with patch.object(transaction, "atomic"):
            manager.get_pending_notification()

        mock_qs.assert_called_once()

    def test_get_notification_data(self):
        """Тест формирования NotificationUsers из MassNotification."""
        notification = MassNotificationFactory(
            subject="Тестовая рассылка",
            message="Текст сообщения",
            priority_order=["telegram", "email"],
        )
        user = UserFactory()
        contact = UserContactModel.objects.create(
            user=user,
            phone_number="+79991234567",
            telegram_profile="https://t.me/testuser",
        )
        recipient = NotificationRecipientFactory(
            notification=notification,
            user=user,
            delivery_status=NotificationRecipient.DeliveryStatus.PENDING,
        )
        notification.pending_recipients = [recipient]

        manager = NotificationManager()
        data = manager._get_notification_date(notification)

        assert isinstance(data, NotificationUsers)
        assert data.id == notification.id
        assert data.subject == "Тестовая рассылка"
        assert data.message == "Текст сообщения"
        assert data.priority == ["telegram", "email"]
        assert len(data.users) == 1
        user_delivery = data.users[0]
        assert isinstance(user_delivery, UserDelivery)
        assert user_delivery.id == user.id
        assert isinstance(user_delivery.contact, UserContact)
        assert user_delivery.contact.email == user.email
        assert user_delivery.contact.telegramm == "https://t.me/testuser"
        assert user_delivery.contact.phone == "+79991234567"

    def test_set_notification_recipient_status(self):
        """Тест обновления статуса получателей."""
        notification = MassNotificationFactory()
        user1 = UserFactory()
        user2 = UserFactory()
        recipient1 = NotificationRecipientFactory(notification=notification, user=user1)
        recipient2 = NotificationRecipientFactory(notification=notification, user=user2)

        manager = NotificationManager()
        data_to_update = NotificationRecipientUpdate(
            delivery_status=NotificationRecipient.DeliveryStatus.SENT,
            delivered_via="email",
        )

        manager._set_notification_recipient_status(
            notification_id=notification.id,
            user_ids=[user1.id, user2.id],
            data=data_to_update,
        )

        recipient1.refresh_from_db()
        recipient2.refresh_from_db()
        assert recipient1.delivery_status == NotificationRecipient.DeliveryStatus.SENT
        assert recipient1.delivered_via == "email"
        assert recipient2.delivery_status == NotificationRecipient.DeliveryStatus.SENT
        assert recipient2.delivered_via == "email"

    def test_get_sender_valid(self):
        """Тест получения валидного отправителя."""
        manager = NotificationManager()

        email_sender = manager.get_sender("email")
        assert email_sender == EmailSender

        telegram_sender = manager.get_sender("telegram")
        assert telegram_sender == TelegramSender

        sms_sender = manager.get_sender("sms")
        assert sms_sender == SmsSender

    def test_get_sender_invalid(self):
        """Тест получения невалидного отправителя."""

        manager = NotificationManager()

        with pytest.raises(
            ValueError, match="'invalid_sender' is not a valid Messengers"
        ):
            manager.get_sender("invalid_sender")

    def test_update_notification_user_date_success(self, mocker):
        """Тест обновления статуса успешно доставленных уведомлений."""

        user_contact = UserContact(email="test@example.com", telegramm=None, phone=None)
        user1_delivered = UserDelivery(id=1, contact=user_contact, delivered=True)
        user2_delivered = UserDelivery(id=2, contact=user_contact, delivered=True)
        user3_not_delivered = UserDelivery(id=3, contact=user_contact, delivered=False)
        data = NotificationUsers(
            id=1,
            subject="Test",
            message="Test",
            priority=["email"],
            users=[user1_delivered, user2_delivered, user3_not_delivered],
        )

        manager = NotificationManager()
        mock_update_status = mocker.patch.object(
            manager, "_set_notification_recipient_status"
        )

        result_data = manager.update_notification_user_date(
            delivered_via="email", data=data
        )

        mock_update_status.assert_called_once_with(
            notification_id=1,
            user_ids=[user1_delivered.id, user2_delivered.id],
            data=NotificationRecipientUpdate(
                delivery_status=NotificationRecipient.DeliveryStatus.SENT,
                delivered_via="email",
            ),
        )

        assert len(result_data.users) == 1
        assert result_data.users[0].id == user3_not_delivered.id

    def test_update_notification_user_date_invalid_delivered_via(self):
        """Тест update_notification_user_date с невалидным delivered_via."""
        manager = NotificationManager()
        data = NotificationUsers(
            id=1, subject="Test", message="Test", priority=["email"], users=[]
        )

        with pytest.raises(ValueError, match="delivered_via parameter must be in"):
            manager.update_notification_user_date(delivered_via="invalid", data=data)

    def test_update_no_chanals_data(self, mocker):
        """Тест обновления статуса пользователей без каналов."""

        contact_with_data = UserContact(
            email="test@example.com", telegramm=None, phone=None
        )
        contact_without_data = UserContact(email=None, telegramm=None, phone=None)

        user1 = UserDelivery(id=1, contact=contact_with_data)
        user2 = UserDelivery(id=2, contact=contact_without_data)
        user3 = UserDelivery(id=3, contact=contact_without_data)
        data = NotificationUsers(
            id=1,
            subject="Test",
            message="Test",
            priority=["email"],
            users=[user1, user2, user3],
        )

        manager = NotificationManager()
        mock_update_status = mocker.patch.object(
            manager, "_set_notification_recipient_status"
        )

        result_data = manager.update_no_chanals_data(data)

        mock_update_status.assert_called_once_with(
            notification_id=1,
            user_ids=[2, 3],
            data=NotificationRecipientUpdate(
                delivery_status=NotificationRecipient.DeliveryStatus.NO_CHANNELS,
                error_message="no chanals",
            ),
        )

        assert len(result_data.users) == 1
        assert result_data.users[0].id == 1

    def test_update_undelivered_notifications(self, mocker):
        """Тест обновления статуса для не доставленных уведомлений."""
        user_contact = UserContact(email="test@example.com", telegramm=None, phone=None)
        user1 = UserDelivery(id=1, contact=user_contact)
        user2 = UserDelivery(id=2, contact=user_contact)
        data = NotificationUsers(
            id=1,
            subject="Test",
            message="Test",
            priority=["email"],
            users=[user1, user2],
        )

        manager = NotificationManager()
        mock_update_status = mocker.patch.object(
            manager, "_set_notification_recipient_status"
        )

        manager.update_undelivered_notifications(data)

        mock_update_status.assert_called_once_with(
            notification_id=1,
            user_ids=[1, 2],
            data=NotificationRecipientUpdate(
                delivery_status=NotificationRecipient.DeliveryStatus.FAILED,
                error_message="Неизвесная ошибка.",
            ),
        )

    def test_update_cant_send(self, mocker):
        """Тест обновления статуса при ошибке отправки и исчерпании каналов."""

        contact_email = UserContact(
            email="test@example.com", telegramm=None, phone=None
        )
        contact_telegram = UserContact(
            email=None, telegramm="https://t.me/user", phone=None
        )
        contact_sms = UserContact(email=None, telegramm=None, phone="+79991234567")

        user1_contact_email = UserDelivery(id=1, contact=contact_email)
        user2_contact_telegram = UserDelivery(id=2, contact=contact_telegram)
        user3_contact_sms = UserDelivery(id=3, contact=contact_sms)
        data = NotificationUsers(
            id=1,
            subject="Test",
            message="Test",
            priority=["email", "telegram", "sms"],
            users=[user1_contact_email, user2_contact_telegram, user3_contact_sms],
        )

        manager = NotificationManager()
        mock_update_status = mocker.patch.object(
            manager, "_set_notification_recipient_status"
        )

        result_data = manager.update_cant_send(
            error="Test error", senders_tryed=["email", "telegram"], data=data
        )

        mock_update_status.assert_called_once_with(
            notification_id=1,
            user_ids=[user1_contact_email.id, user2_contact_telegram.id],
            data=NotificationRecipientUpdate(
                delivery_status=NotificationRecipient.DeliveryStatus.FAILED,
                delivered_via="telegram",
                error_message="Test error",
            ),
        )

        assert len(result_data.users) == 1
        assert result_data.users[0].id == user3_contact_sms.id

    def test_filter_by(self):
        """Тест вспомогательной функции _filter_by."""
        contact = UserContact(
            email="test@example.com",
            telegramm="https://t.me/user",
            phone="+79991234567",
        )
        user1_not_delivered = UserDelivery(id=1, contact=contact, delivered=False)
        user2_delivered = UserDelivery(id=2, contact=contact, delivered=True)
        user3_not_delivered = UserDelivery(id=3, contact=contact, delivered=False)
        data = NotificationUsers(
            id=1,
            subject="Test",
            message="Test",
            priority=["email"],
            users=[user1_not_delivered, user2_delivered, user3_not_delivered],
        )

        manager = NotificationManager()

        def filter_func(u):
            return u.delivered

        returned_ids = manager._filter_by(by_func=filter_func, data=data)

        assert set(returned_ids) == {user1_not_delivered.id, user3_not_delivered.id}
        assert len(data.users) == 1
        assert data.users[0].id == user2_delivered.id

    def test_update_notification_completed(self):
        """Тест обновления статуса рассылки до COMPLETED."""
        user = UserFactory()
        notification = MassNotificationFactory(
            status=MassNotification.Status.PROCESSING
        )
        NotificationRecipientFactory(notification=notification, user=user)

        data = NotificationUsers(
            id=notification.id,
            subject="Test",
            message="Test",
            priority=["email"],
            users=[],
        )

        manager = NotificationManager()
        manager.update_notification(data)

        notification.refresh_from_db()
        assert notification.status == MassNotification.Status.COMPLETED
        assert notification.immediately is False

    def test_update_notification_failed(self):
        """Тест обновления статуса рассылки до FAILED."""

        user = UserFactory()
        notification = MassNotificationFactory(
            status=MassNotification.Status.PROCESSING
        )
        NotificationRecipientFactory(notification=notification, user=user)
        contact = UserContact(
            email="test@example.com",
            telegramm="https://t.me/user",
            phone="+79991234567",
        )
        user_delivery = UserDelivery(id=user.id, contact=contact)
        data = NotificationUsers(
            id=notification.id,
            subject="Test",
            message="Test",
            priority=["email"],
            users=[user_delivery],
        )

        manager = NotificationManager()
        manager.update_notification(data)

        notification.refresh_from_db()
        assert notification.status == MassNotification.Status.FAILED
        assert notification.immediately is False

    def test_send_calls_correct_methods(self, mocker):
        """Тест основного метода send - вызывает ли он нужные методы."""

        notification = MassNotificationFactory(
            status=MassNotification.Status.PENDING, immediately=False
        )
        user = UserFactory()
        NotificationRecipientFactory(
            notification=notification,
            user=user,
            delivery_status=NotificationRecipient.DeliveryStatus.PENDING,
        )

        manager = NotificationManager(id=notification.id)

        mock_get_pending = mocker.patch.object(
            manager, "get_pending_notification", return_value=[notification]
        )
        mock_get_data = mocker.patch.object(
            manager, "_get_notification_date", return_value=Mock()
        )
        mock_send_notif = mocker.patch.object(
            manager, "_send_notification", return_value=True
        )
        mock_update_notif = mocker.patch.object(manager, "update_notification")

        manager.send()

        mock_get_pending.assert_called_once()
        mock_get_data.assert_called_once_with(notification=notification)
        mock_send_notif.assert_called_once_with(data=mock_get_data.return_value)
        mock_update_notif.assert_called_once_with(data=mock_get_data.return_value)

    def test_send_notification_success(self, mocker):
        """Тест _send_notification - успешная отправка."""

        contact = UserContact(email="test@example.com", telegramm=None, phone=None)
        user1_delivered = UserDelivery(id=1, contact=contact, delivered=True)
        user2_not_delivered = UserDelivery(id=2, contact=contact, delivered=False)
        original_data = NotificationUsers(
            id=1,
            subject="Test",
            message="Test",
            priority=["email"],
            users=[user1_delivered, user2_not_delivered],
        )

        manager = NotificationManager()

        mock_sender_class = mocker.Mock()
        mock_sender_instance = mocker.Mock()
        mock_sender_class.return_value = mock_sender_instance
        mock_sender_instance.send_notification.return_value = [user2_not_delivered]

        mock_get_sender = mocker.patch.object(
            manager, "get_sender", return_value=mock_sender_class
        )
        mocker.patch.object(
            manager, "update_no_chanals_data", return_value=original_data
        )
        data_after_update_date = NotificationUsers(
            id=1,
            subject="Test",
            message="Test",
            priority=["email"],
            users=[user2_not_delivered],
        )
        mock_update_date = mocker.patch.object(
            manager,
            "update_notification_user_date",
            return_value=data_after_update_date,
        )
        mock_update_cant_send = mocker.patch.object(manager, "update_cant_send")
        mock_update_undelivered = mocker.patch.object(
            manager, "update_undelivered_notifications"
        )

        result = manager._send_notification(original_data)

        mock_get_sender.assert_called_once_with(name="email")
        mock_sender_instance.send_notification.assert_called_once_with(
            subject="Test", message="Test", users=[user1_delivered, user2_not_delivered]
        )
        mock_update_date.assert_called_once_with(
            delivered_via="email", data=original_data
        )
        mock_update_cant_send.assert_not_called()
        mock_update_undelivered.assert_called_once_with(data=data_after_update_date)
        assert result is False

    def test_send_notification_failure_and_retry(self, mocker):
        """Тест _send_notification - ошибка отправки, попытка через другой канал."""

        contact = UserContact(
            email="test@example.com", telegramm="https://t.me/user", phone=None
        )
        user = UserDelivery(id=1, contact=contact, delivered=False)
        original_data = NotificationUsers(
            id=1,
            subject="Test",
            message="Test",
            priority=["email", "telegram"],
            users=[user],
        )

        manager = NotificationManager()

        mock_email_sender_class = mocker.Mock()
        mock_email_sender_instance = mocker.Mock()
        mock_email_sender_class.return_value = mock_email_sender_instance
        mock_email_sender_instance.send_notification.side_effect = Exception(
            "Email failed"
        )

        mock_telegram_sender_class = mocker.Mock()
        mock_telegram_sender_instance = mocker.Mock()
        mock_telegram_sender_class.return_value = mock_telegram_sender_instance
        mock_telegram_sender_instance.send_notification.return_value = []

        def side_effect_get_sender(name):
            if name == "email":
                return mock_email_sender_class
            elif name == "telegram":
                return mock_telegram_sender_class
            else:
                raise ValueError("Unknown")

        mock_get_sender = mocker.patch.object(
            manager, "get_sender", side_effect=side_effect_get_sender
        )
        mocker.patch.object(
            manager, "update_no_chanals_data", return_value=original_data
        )
        data_after_telegram = NotificationUsers(
            id=1,
            subject="Test",
            message="Test",
            priority=["email", "telegram"],
            users=[],
        )
        mock_update_date = mocker.patch.object(
            manager, "update_notification_user_date", return_value=data_after_telegram
        )
        mock_update_cant_send = mocker.patch.object(manager, "update_cant_send")
        mock_update_undelivered = mocker.patch.object(
            manager, "update_undelivered_notifications"
        )

        result = manager._send_notification(original_data)

        assert mock_get_sender.call_count == 2
        mock_get_sender.assert_has_calls([call(name="email"), call(name="telegram")])
        mock_email_sender_instance.send_notification.assert_called_once_with(
            subject="Test", message="Test", users=[user]
        )
        mock_telegram_sender_instance.send_notification.assert_called_once_with(
            subject="Test", message="Test", users=[user]
        )
        mock_update_date.assert_called_once_with(
            delivered_via="telegram", data=original_data
        )
        mock_update_cant_send.assert_called_once_with(
            error="Email failed",
            senders_tryed=["email", "telegram"],
            data=original_data,
        )
        mock_update_undelivered.assert_not_called()
        assert result is True

    def test_get_pending_notification_with_recipients(self, mocker):
        """Тест получения рассылки с получателями через prefetch."""

        notification = MassNotificationFactory(
            status=MassNotification.Status.PENDING, immediately=True, scheduled_for=None
        )
        user_with_contact = UserFactory()
        UserContactModel.objects.create(
            user=user_with_contact, telegram_profile="https://t.me/testuser"
        )
        NotificationRecipientFactory(
            notification=notification,
            user=user_with_contact,
            delivery_status=NotificationRecipient.DeliveryStatus.PENDING,
        )
        another_user = UserFactory()
        NotificationRecipientFactory(
            notification=notification,
            user=another_user,
            delivery_status=NotificationRecipient.DeliveryStatus.FAILED,
        )
        manager = NotificationManager(id=notification.id)

        initial_status = notification.status
        initial_immediately = notification.immediately

        queryset = manager.get_pending_notification()

        fetched_notification = queryset.first()
        assert fetched_notification.id == notification.id
        prefetched_recipients = fetched_notification.pending_recipients
        assert len(prefetched_recipients) == 2
        statuses = {r.delivery_status for r in prefetched_recipients}
        expected_statuses = {
            NotificationRecipient.DeliveryStatus.PENDING,
            NotificationRecipient.DeliveryStatus.FAILED,
        }
        assert statuses == expected_statuses

        notification.refresh_from_db()
        assert notification.status != initial_status
        assert notification.status == MassNotification.Status.PROCESSING
        assert notification.immediately != initial_immediately
        assert notification.immediately is False
        assert notification.started_at is not None
