from django.contrib.auth import get_user_model
from django.core.validators import MinLengthValidator
from django.db import models

User = get_user_model()


class MassNotification(models.Model):
    """
    Модель для хранения данных о массовых рассылках уведомлений.

    Основная сущность, представляющая собой рассылку сообщений множеству пользователей
    через различные каналы связи (email, telegram, sms) с учетом приоритетов.

    Attributes:
        subject (CharField): Тема уведомления, обязательное поле (1-200 символов)
        message (TextField): Текст сообщения для рассылки
        users (ManyToManyField): Связь с пользователями через промежуточную модель NotificationRecipient
        immediately (BooleanField): Флаг немедленной отправки рассылки
        priority_order (JSONField): Порядок приоритета каналов отправки в формате JSON
        status (CharField): Текущий статус выполнения рассылки
        created_by (ForeignKey): Пользователь, создавший рассылку
        total_recipients (PositiveIntegerField): Общее количество получателей
        sent_count (PositiveIntegerField): Количество успешно отправленных уведомлений
        failed_count (PositiveIntegerField): Количество неудачных отправок
        created_at (DateTimeField): Дата и время создания записи
        scheduled_for (DateTimeField): Дата и время запланированной отправки
        started_at (DateTimeField): Время фактического начала отправки
        completed_at (DateTimeField): Время завершения рассылки

    Examples:
        >>> notification = MassNotification.objects.create(
        ...     subject="Важное обновление",
        ...     message="Система будет обновлена завтра",
        ...     immediately=True,
        ...     priority_order=["email", "telegram"]
        ... )
        >>> notification.users.add(user1, user2, user3)
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает отправки"
        PROCESSING = "processing", "В процессе отправки"
        COMPLETED = "completed", "Завершена"
        FAILED = "failed", "Завершена с ошибками"
        CANCELLED = "cancelled", "Отменена"

    subject = models.CharField(
        max_length=200,
        validators=[MinLengthValidator(1)],
        verbose_name="Тема уведомления",
        help_text="Тема уведомления (1-200 символов)",
    )
    message = models.TextField(
        verbose_name="Текст сообщения", help_text="Текст сообщения для рассылки"
    )
    users = models.ManyToManyField(
        User,
        through="NotificationRecipient",
        related_name="mass_notifications",
        verbose_name="Пользователи для рассылки",
        help_text="Пользователи, которым предназначена рассылка",
    )
    immediately = models.BooleanField(
        default=False,
        verbose_name="Немедленная отправка",
        help_text="Отправить рассылку немедленно",
    )
    priority_order = models.JSONField(
        default=["email", "telegram", "sms"],
        verbose_name="Порядок приоритета каналов",
        help_text="Порядок каналов отправки в формате JSON массива",
    )
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Статус рассылки",
        help_text="Текущий статус выполнения рассылки",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_notifications",
        verbose_name="Создатель рассылки",
        help_text="Пользователь, создавший рассылку",
    )
    total_recipients = models.PositiveIntegerField(
        default=0,
        verbose_name="Всего получателей",
        help_text="Общее количество получателей рассылки",
    )
    sent_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Отправлено",
        help_text="Количество успешно отправленных уведомлений",
    )
    failed_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Ошибок отправки",
        help_text="Количество неудачных отправок",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    scheduled_for = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Запланирована на",
        help_text="Дата и время запланированной отправки",
    )
    started_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Время начала отправки"
    )
    completed_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Время завершения"
    )

    class Meta:
        db_table = "mass_notifications"
        verbose_name = "Массовая рассылка"
        verbose_name_plural = "Массовые рассылки"
        indexes = [
            models.Index(fields=["status", "scheduled_for"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Рассылка #{self.id}: {self.subject}"

    def save(self, *args, **kwargs):
        """Переопределение save для автоматического расчета получателей."""

        if self.pk:
            self.total_recipients = self.recipients.count()
        super().save(*args, **kwargs)


class NotificationRecipient(models.Model):
    """
    Промежуточная модель для связи рассылки с пользователями.

    Хранит индивидуальный статус отправки и информацию о доставке
    для каждого пользователя в рамках массовой рассылки.

    Attributes:
        notification (ForeignKey): Ссылка на родительскую рассылку
        user (ForeignKey): Пользователь-получатель рассылки
        delivery_status (CharField): Статус доставки для конкретного пользователя
        delivered_via (CharField): Канал, через который было отправлено уведомление
        error_message (TextField): Описание ошибки при неудачной отправке
        sent_at (DateTimeField): Время фактической отправки уведомления

    Examples:
        >>> recipient = NotificationRecipient.objects.create(
        ...     notification=notification,
        ...     user=user,
        ...     delivery_status=NotificationRecipient.DeliveryStatus.PENDING
        ... )
    """

    class DeliveryStatus(models.TextChoices):
        PENDING = "pending", "Ожидает отправки"
        SENT = "sent", "Отправлено"
        FAILED = "failed", "Ошибка отправки"
        NO_CHANNELS = "no_channels", "Нет доступных каналов"

    notification = models.ForeignKey(
        MassNotification,
        on_delete=models.CASCADE,
        related_name="recipients",
        verbose_name="Рассылка",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notification_recipients",
        verbose_name="Пользователь",
    )
    delivery_status = models.CharField(
        max_length=15,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
        verbose_name="Статус доставки",
    )
    delivered_via = models.CharField(
        max_length=10,
        choices=[
            ("email", "Email"),
            ("telegram", "Telegram"),
            ("sms", "SMS"),
        ],
        null=True,
        blank=True,
        verbose_name="Канал доставки",
    )
    error_message = models.TextField(
        blank=True,
        verbose_name="Сообщение об ошибке",
        help_text="Описание ошибки при неудачной отправке",
    )
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name="Время отправки")

    class Meta:
        db_table = "notification_recipients"
        verbose_name = "Получатель рассылки"
        verbose_name_plural = "Получатели рассылок"
        unique_together = ["notification", "user"]
        indexes = [
            models.Index(fields=["delivery_status", "sent_at"]),
            models.Index(fields=["user", "sent_at"]),
        ]

    def __str__(self):
        return f"Получатель {self.user_id} для рассылки #{self.notification_id}"
