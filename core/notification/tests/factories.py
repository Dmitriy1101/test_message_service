import factory
from django.contrib.auth import get_user_model
from notification.models import MassNotification, NotificationRecipient
from users.tests.factories import UserFactory

User = get_user_model()


class MassNotificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MassNotification

    subject = factory.Sequence(lambda n: f"Тестовая рассылка {n}")
    message = "Текст тестового сообщения."
    immediately = False
    priority_order = ["email", "telegram", "sms"]
    status = MassNotification.Status.PENDING
    created_by = factory.SubFactory(UserFactory)
    scheduled_for = None


class NotificationRecipientFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = NotificationRecipient

    notification = factory.SubFactory(MassNotificationFactory)
    user = factory.SubFactory(UserFactory)
    delivery_status = NotificationRecipient.DeliveryStatus.PENDING
    delivered_via = "email"
    error_message = ""
    sent_at = None
