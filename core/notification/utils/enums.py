from enum import Enum


class Messengers(Enum):
    """
    Перечисление доступных каналов доставки уведомлений.

    Используется для типизированного указания мессенджеров в коде
    и обеспечения корректной работы системы отправки.

    Attributes:
        EMAIL: Электронная почта
        TELEGRAM: Telegram мессенджер
        SMS: SMS сообщения
    """

    EMAIL = "email"
    TELEGRAM = "telegram"
    SMS = "sms"
