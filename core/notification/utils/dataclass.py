from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel
from notification.models import NotificationRecipient


class UserContact(BaseModel):
    """
    Модель контактной информации пользователя для доставки уведомлений.

    Attributes:
        email: Адрес электронной почты пользователя (опционально)
        telegramm: Имя пользователя в Telegram (опционально)
        phone: Номер телефона для SMS-уведомлений (опционально)

    Note:
        Все поля опциональны, но хотя бы один контакт должен быть указан
        для возможности доставки уведомлений.
    """

    email: Optional[str] = None
    telegramm: Optional[str] = None
    phone: Optional[str] = None

    def __bool__(self) -> bool:
        if self.email or self.telegramm or self.phone:
            return True
        return False


class UserDelivery(BaseModel):
    """
    Модель пользователя с информацией о доставке уведомлений.

    Attributes:
        id: Уникальный идентификатор пользователя
        contact: Контактная информация пользователя
        delivered: Флаг успешной доставки уведомления (по умолчанию False)

    Examples:
        >>> user = UserDelivery(
        ...     id=1,
        ...     contact=UserContact(email="user@example.com", phone="+79991234567"),
        ...     delivered=False
        ... )
    """

    id: int
    contact: UserContact
    delivered: Optional[bool] = False


class NotificationUsers(BaseModel):
    """
    Модель массовой рассылки уведомлений с получателями и приоритетом доставки.

    Attributes:
        id: Уникальный идентификатор рассылки
        subject: Тема уведомления
        message: Текст сообщения для рассылки
        users: Список пользователей-получателей  с контактной информацией
        priority: Порядок приоритета каналов доставки. Определяет последовательность
                 попыток отправки: email → telegram → SMS

    Examples:
        >>> notification = NotificationUsers(
        ...     id=1,
        ...     subject="Важное обновление",
        ...     message="Система будет обновлена завтра",
        ...     users=[user1, user2],
        ...     priority=["email", "telegram", "sms"]
        ... )

    Note:
        Каналы доставки в priority должны быть уникальными и содержать только
        допустимые значения: "email", "telegram", "sms".
    """

    id: int
    subject: str
    message: str
    users: list[UserDelivery]
    priority: list[Literal["email", "telegram", "sms"]]


class NotificationRecipientUpdate(BaseModel):
    """
    Модель результата доставки уведомления для массового обновления статусов.

    Используется для фиксации результата попытки отправки уведомления
    конкретному пользователю или группе пользователей.

    Attributes:
        delivery_status: Статус доставки уведомления (по умолчанию SENT)
        error_message: Сообщение об ошибке при неудачной доставке (опционально)
        delivered_via: Канал, через который было доставлено уведомление
        sent_at: Дата и время фактической отправки уведомления

    Examples:
        >>> # Успешная доставка по email
        >>> result = NotificationRecipientUpdate(
        ...     delivery_status=NotificationRecipient.DeliveryStatus.SENT,
        ...     delivered_via="email",
        ...     sent_at=datetime.now()
        ... )
        >>>
        >>> # Неудачная доставка с описанием ошибки
        >>> result = NotificationRecipientUpdate(
        ...     delivery_status=NotificationRecipient.DeliveryStatus.FAILED,
        ...     error_message="SMTP server timeout",
        ...     delivered_via="email",
        ...     sent_at=datetime.now()
        ... )

    Note:
        - Для статуса FAILED рекомендуется указывать error_message
        - Поле sent_at должно соответствовать фактическому времени отправки
        - user_ids не может быть пустым списком
    """

    delivery_status: NotificationRecipient.DeliveryStatus = (
        NotificationRecipient.DeliveryStatus.SENT
    )
    error_message: Optional[str] = ""
    delivered_via: Optional[Literal["email", "telegram", "sms"]] = None
    sent_at: Optional[datetime] = None
