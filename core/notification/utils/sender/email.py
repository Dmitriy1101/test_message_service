from notification.utils.dataclass import UserDelivery
from notification.utils.sender.abc import SenderABC
from django.core.mail import EmailMessage
from django.conf import settings


class EmailSender(SenderABC):
    """
    Реализация отправителя уведомлений через электронную почту.

    Класс предоставляет функционал для массовой отправки email-уведомлений
    пользователям через Django email backend. Использует скрытую копию (BCC)
    для сохранения конфиденциальности получателей.

    Особенности:
    - Массовая отправка через BCC для скрытия списка получателей
    - Интеграция с Django email backend (SMTP, Console, File, etc.)
    - Автоматическое использование DEFAULT_FROM_EMAIL из настроек
    - Простая и эффективная обработка статусов доставки

    Зависимости:
        - Настройка DEFAULT_FROM_EMAIL в settings.py
        - Конфигурация EMAIL_BACKEND в settings.py
        - Наличие контактов email у пользователей

    Пример использования:
        ```python
        sender = EmailSender()
        users = [
            UserDelivery(contact=Contact(email="user1@example.com"), delivered=False),
            UserDelivery(contact=Contact(email="user2@example.com"), delivered=False)
        ]
        result_users = sender.send_notification(
            subject="Важное уведомление",
            message="Текст сообщения с важной информацией",
            users=users
        )
        ```
    """

    def _send(self, subject: str, message: str, contacts: list[str]) -> list[str]:
        """
        Отправляет email-уведомление списку получателей через Django EmailMessage.

        Создает одно email-сообщение со всеми получателями в скрытой копии (BCC)
        для сохранения конфиденциальности. Отправка происходит через настроенный
        в Django email backend.

        Args:
            subject (str): Тема email-сообщения. Должна быть информативной и краткой.
                         Рекомендуемая длина до 78 символов.
            message (str): Текст email-сообщения. Может содержать plain-text
                          или HTML (если content_subtype='html').
            contacts (list[str]): Список email-адресов получателей. Должны быть
                                 валидными email-адресами в соответствии с RFC 5322.

        Returns:
            list[str]: Список успешно отправленных email-адресов. В текущей реализации
                      возвращает все переданные контакты при успешной отправке,
                      либо None при возникновении ошибки.

        Raises:
            SMTPException: При ошибках подключения к SMTP-серверу
            ConnectionError: При проблемах сетевого соединения
            EmailSendingError: При ошибках валидации или отправки email
        """

        email_msg = EmailMessage(
            subject=subject,
            body=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            bcc=contacts,
        )
        if email_msg.send():
            return contacts

    def set_status(
        self, sucsess: list[str], users: list[UserDelivery]
    ) -> list[UserDelivery]:
        """
        Обновляет статусы доставки email-уведомлений для пользователей.
        
        Сравнивает email-адреса пользователей со списком успешно отправленных
        адресов и обновляет флаги доставки. Только пользователи с email-адресами,
        присутствующими в списке успешных отправок, помечаются как доставленные.
        
        Args:
            sucsess (list[str]): Список email-адресов, на которые уведомление
                                было успешно отправлено. Должен содержать
                                валидные email-адреса в том же формате,
                                что и в контактах пользователей.
            users (list[UserDelivery]): Исходный список пользователей для
                                       обновления статусов доставки.
        
        Returns:
            list[UserDelivery]: Обновленный список пользователей, где:
                               - delivered=True для пользователей с email,
                                 присутствующим в списке success
                               - delivered=False для всех остальных пользователей
        
        """
        for user in users:
            if user.contact.email in sucsess:
                user.delivered = True
        return users

    def _get_contact(self, users: list[UserDelivery]) -> list[str]:
        """
        Извлекает email-адреса из списка пользователей.
        
        Фильтрует пользователей, оставляя только тех, у кого указан email-адрес,
        и возвращает список этих адресов. Пользователи без email или с пустым
        email-адресом исключаются из результата.
        
        Args:
            users (list[UserDelivery]): Список пользователей с контактной информацией.
                                       Каждый пользователь должен иметь атрибут
                                       contact с полем email.
        
        Returns:
            list[str]: Список валидных email-адресов пользователей. Список может
                      быть пустым, если ни у одного пользователя нет email-адреса.
        
        """

        return [user.contact.email for user in users if user.contact.email]
