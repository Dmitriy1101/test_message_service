"""
Модуль управления системой массовых уведомлений.

Содержит основные компоненты для обработки и отправки уведомлений через
различные каналы связи (email, telegram, SMS) с поддержкой приоритетов
и отслеживанием статуса доставки.

Notification management system module.

Contains core components for processing and sending notifications through
various communication channels (email, telegram, SMS) with priority support
and delivery status tracking.
"""

from datetime import datetime
from typing import Callable, Literal
from notification.utils.dataclass import UserDelivery
from notification.models import MassNotification, NotificationRecipient
from django.db.models import QuerySet, Prefetch, Q
from django.utils import timezone
from django.db import transaction
from .sender import EmailSender, SmsSender, TelegramSender
from .dataclass import (
    UserContact,
    UserDelivery,
    NotificationUsers,
    NotificationRecipientUpdate,
)
from logging import Logger, getLogger
from .enums import Messengers
from .protocol import Sender

log: Logger = getLogger(__name__)


class NotificationManager:
    """
    Менеджер для обработки и отправки массовых уведомлений.

    Осуществляет управление жизненным циклом уведомлений: извлечение ожидающих
    рассылок, фильтрация получателей, отправка через различные каналы связи
    и обновление статусов доставки.

    Attributes:
        id (int): Идентификатор конкретной рассылки для обработки (опционально)

    Example:
        >>> manager = NotificationManager()
        >>> manager.send()  # Запуск обработки всех ожидающих рассылок
    """

    def __init__(self, id: int = None) -> None:
        self.id: int = id

    def get_pending_notification(self) -> QuerySet:
        """
        Получает набор рассылок, готовых к обработке.

        Блокирует выбранные записи для предотвращения конкурентного выполнения.
        Автоматически обновляет статус рассылок на 'PROCESSING'.

        Returns:
            QuerySet: Набор объектов MassNotification, готовых к отправке

        Note:
            Использует транзакцию и SELECT FOR UPDATE для thread-safe выполнения
        """

        now: datetime = timezone.now()
        with transaction.atomic():
            queryset: QuerySet
            queryset = MassNotification.objects.select_for_update()
            if self.id:
                queryset = queryset.filter(id=self.id)
            else:
                queryset = queryset.filter(
                    Q(scheduled_for__isnull=True) | Q(scheduled_for__lte=now),
                    status=MassNotification.Status.PENDING,
                    immediately=False,
                )
            if not queryset.exists():
                log.debug(
                    "len(queryset): %s, queryset.exists(): %s",
                    len(queryset),
                    queryset.exists(),
                )
                return MassNotification.objects.none()
            notification_ids = list(queryset.values_list("id", flat=True))

            log.debug("Work with nitifications: %s", notification_ids)
            queryset.update(
                status=MassNotification.Status.PROCESSING,
                immediately=False,
                started_at=now,
            )
            return (
                MassNotification.objects.select_related("created_by")
                .prefetch_related(
                    Prefetch(
                        "recipients",
                        queryset=NotificationRecipient.objects.select_related(
                            "user__contact"
                        ).filter(delivery_status__in=["pending", "failed"]),
                        to_attr="pending_recipients",
                    )
                )
                .filter(id__in=notification_ids)
            )

    def _get_notification_date(
        self, notification: MassNotification
    ) -> NotificationUsers:
        """
        Формирует объект с данными для отправки уведомления.

        Args:
            notification: Объект массового уведомления

        Returns:
            NotificationUsers: Структурированные данные для отправки
        """

        log.debug("type notification: %s", type(notification))
        return NotificationUsers(
            id=notification.id,
            priority=notification.priority_order,
            subject=notification.subject,
            message=notification.message,
            users=[
                UserDelivery(
                    id=state.user.id,
                    contact=UserContact(
                        email=state.user.email,
                        telegramm=state.user.contact.telegram_profile
                        if hasattr(state.user, "contact")
                        else None,
                        phone=state.user.contact.phone_number
                        if hasattr(state.user, "contact")
                        else None,
                    ),
                )
                for state in notification.pending_recipients
            ],
        )

    def _set_notification_recipient_status(
        self,
        notification_id: int,
        user_ids: list[int],
        data: NotificationRecipientUpdate,
    ) -> None:
        """
        Обновляет статусы доставки для получателей уведомления.

        Args:
            notification_id: ID рассылки
            user_ids: Список ID пользователей для обновления
            data: Данные для обновления статуса
        """

        data_model = data.model_dump()
        log.debug(
            "Update notification ID: %s, users: %s, data: %s",
            notification_id,
            user_ids,
            data_model,
        )
        NotificationRecipient.objects.filter(
            notification=notification_id, user__in=user_ids
        ).update(**data_model)

    def get_sender(self, name: str) -> type[Sender]:
        """
        Возвращает класс отправителя по имени канала доставки.

        Args:
            name: Имя канала доставки ('email', 'telegram', 'sms')

        Returns:
            type[Sender]: Класс отправителя, реализующий протокол Sender

        Raises:
            ValueError: Если передан неизвестный тип отправителя
        """

        sender: Sender = Messengers(name)
        if sender == Messengers.EMAIL:
            return EmailSender
        elif sender == Messengers.TELEGRAM:
            return TelegramSender
        elif sender == Messengers.SMS:
            return SmsSender
        raise ValueError("Unknown notification sending service name.")

    def update_notification_user_date(
        self,
        delivered_via: Literal["email", "telegram", "sms"],
        data: NotificationUsers,
    ) -> NotificationUsers:
        """
        Обновляет статус успешно доставленных уведомлений.

        Фильтрует пользователей с успешной доставкой, обновляет их статус в БД
        и возвращает оставшихся пользователей для повторных попыток отправки.

        Args:
            delivered_via: Канал доставки, через который было отправлено уведомление
            data: Данные рассылки с обновленными статусами доставки

        Returns:
            NotificationUsers: Данные с пользователями, не получившими уведомление

        Raises:
            ValueError: При некорректном значении delivered_via
        """

        if delivered_via not in ("email", "telegram", "sms"):
            raise ValueError(
                'delivered_via parameter must be in ("email", "telegram", "sms")'
            )
        for_update: list[int] = self._filter_by(
            by_func=lambda x: (not x.delivered), data=data
        )
        if for_update:
            self._set_notification_recipient_status(
                notification_id=data.id,
                user_ids=for_update,
                data=NotificationRecipientUpdate(
                    delivery_status=NotificationRecipient.DeliveryStatus.SENT,
                    delivered_via=delivered_via,
                ),
            )
        return data

    def update_no_chanals_data(self, data: NotificationUsers) -> NotificationUsers:
        """
        Обрабатывает пользователей без доступных каналов доставки.

        Удаляет из рассылки пользователей, у которых отсутствуют все указанные
        каналы связи, и фиксирует это в базе данных.

        Args:
            data: Данные рассылки для обработки

        Returns:
            NotificationUsers: Данные с пользователями, имеющими каналы доставки
        """

        none_chanel: list[int] = self._filter_by(by_func=lambda x: x.contact, data=data)
        if none_chanel:
            self._set_notification_recipient_status(
                notification_id=data.id,
                user_ids=none_chanel,
                data=NotificationRecipientUpdate(
                    delivery_status=NotificationRecipient.DeliveryStatus.NO_CHANNELS,
                    error_message="no chanals",
                ),
            )
        return data

    def update_undelivered_notifications(self, data: NotificationUsers) -> None:
        """
        Обрабатывает пользователей, которым не удалось доставить уведомление.

        Вызывается когда все попытки отправки исчерпаны. Фиксирует финальный
        статус ошибки для оставшихся пользователей.

        Args:
            data: Данные рассылки с пользователями, не получившими уведомление
        """

        last_user_id: list[int] = [user.id for user in data.users]
        self._set_notification_recipient_status(
            notification_id=data.id,
            user_ids=last_user_id,
            data=NotificationRecipientUpdate(
                delivery_status=NotificationRecipient.DeliveryStatus.FAILED,
                error_message="Неизвесная ошибка.",
            ),
        )

    def update_cant_send(
        self,
        error: str,
        senders_tryed: list[Literal["email", "telegram", "sms"]],
        data: NotificationUsers,
    ) -> NotificationUsers:
        """
        Обрабатывает ошибки отправки при исчерпании доступных каналов.

        Определяет пользователей, для которых больше не осталось доступных
        каналов доставки, и фиксирует ошибку отправки.

        Args:
            error: Сообщение об ошибке
            senders_tryed: Список уже опробованных каналов доставки
            data: Данные рассылки для обработки

        Returns:
            NotificationUsers: Данные с пользователями для повторной попытки
        """

        def is_not_end(user: UserDelivery) -> bool:
            avalibale_senders: list[str] | None = [
                i for i in data.priority if i not in senders_tryed
            ]
            if not avalibale_senders:
                return False
            elif user.contact.telegramm and "telegram" not in avalibale_senders:
                return True
            elif user.contact.email and "email" not in avalibale_senders:
                return True
            elif user.contact.phone and "sms" not in avalibale_senders:
                return True
            return False

        this_is_fail_id = self._filter_by(by_func=is_not_end, data=data)

        self._set_notification_recipient_status(
            notification_id=data.id,
            user_ids=this_is_fail_id,
            data=NotificationRecipientUpdate(
                delivery_status=NotificationRecipient.DeliveryStatus.FAILED,
                delivered_via=senders_tryed[-1],
                error_message=error,
            ),
        )

    def _filter_by(self, by_func: Callable, data: NotificationUsers) -> list[int]:
        """
        Фильтрует пользователей по заданной функции-предикату.

        Args:
            by_func: Функция-фильтр, принимающая UserDelivery и возвращающая bool
            data: Данные рассылки для фильтрации

        Returns:
            list[int]: Список ID пользователей, не прошедших фильтрацию
        """

        fail_check: list[int] = []
        good_check: list[UserDelivery] = []
        for user in data.users:
            if by_func(user):
                good_check.append(user)
            else:
                fail_check.append(user.id)
        data.users = good_check
        return fail_check

    def update_notification(self, data: NotificationUsers) -> None:
        """
        Обновляет общий статус рассылки после завершения отправки.

        Args:
            data: Данные рассылки после обработки всех пользователей
        """

        MassNotification.objects.filter(id=data.id).update(
            status=MassNotification.Status.COMPLETED
            if not data.users
            else MassNotification.Status.FAILED,
            immediately=False,
        )

    def send(self):
        """
        Основной метод запуска обработки и отправки рассылок.

        Извлекает ожидающие рассылки, обрабатывает каждую и обновляет финальные статусы.
        """

        query = self.get_pending_notification()
        for notification in query:
            data = self._get_notification_date(notification=notification)
            log.info("Start sending notification ID: %s", data.id)
            self._send_notification(data=data)
            self.update_notification(data=data)

    def _send_notification(self, data: NotificationUsers) -> bool:
        """
        Выполняет отправку уведомления через доступные каналы связи.

        Осуществляет отправку согласно приоритету каналов с обработкой ошибок
        и повторными попытками через альтернативные каналы.

        Args:
            data: Данные рассылки для отправки

        Returns:
            bool: True если все уведомления доставлены, иначе False
        """

        log.debug(
            "Notification ID: %s has chanels: %s and %s users count.",
            data.id,
            data.priority,
            len(data.users),
        )
        data = self.update_no_chanals_data(data=data)
        try_send: list[Literal["email", "telegram", "sms"]] = []
        log.debug(
            "Notification ID: %s, %s users has available communication channels",
            data.id,
            len(data.users),
        )
        for name in data.priority:
            try_send.append(name)
            sender: type[Sender] = self.get_sender(name=name)
            try:
                data.users = sender().send_notification(
                    subject=data.subject, message=data.message, users=data.users
                )
                data = self.update_notification_user_date(delivered_via=name, data=data)
            except Exception as e:
                self.update_cant_send(error=str(e), senders_tryed=try_send, data=data)
        if data.users:
            self.update_undelivered_notifications(data=data)
            return False
        return True
