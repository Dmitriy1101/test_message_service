from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import MassNotification, NotificationRecipient

User = get_user_model()


class MassNotificationCreateSerializer(serializers.ModelSerializer):
    """
    Сериализатор для создания массовых рассылок уведомлений.

    Обрабатывает следующие поля:
    - subject: Тема уведомления (обязательное)
    - message: Текст сообщения (обязательное)
    - user_id: Список ID пользователей-получателей (обязательное, write-only)
    - immediately: Флаг немедленной отправки (по умолчанию False)
    - priority_order: Порядок приоритета каналов отправки (по умолчанию ["email", "telegram", "sms"])
    - scheduled_for: Дата и время запланированной отправки (опциональное)

    Особенности:
    - Оптимизирован для работы со связью ManyToMany через промежуточную модель NotificationRecipient
    - Использует один запрос к БД для валидации и создания получателей
    - Автоматически устанавливает значения по умолчанию для необязательных полей
    """

    user_id = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        source="users",
        help_text="ID пользователей для рассылки",
    )

    class Meta:
        model = MassNotification
        fields = [
            "subject",
            "message",
            "user_id",
            "immediately",
            "priority_order",
            "scheduled_for",
        ]
        extra_kwargs = {
            "immediately": {"default": False},
            "priority_order": {"default": ["email", "telegram", "sms"]},
        }

    def validate_priority_order(self, value: list) -> list:
        """
        Валидация порядка приоритета каналов отправки.

        Args:
            value: Список каналов отправки

        Returns:
            list: Валидированный список каналов

        Raises:
            ValidationError: Если есть дубликаты или невалидные каналы
        """

        if len(value) != len(set(value)):
            raise serializers.ValidationError(
                "Порядок приоритета должен содержать уникальные значения."
            )

        valid_channels = {"email", "telegram", "sms"}
        invalid_channels = set(value) - valid_channels

        if invalid_channels:
            raise serializers.ValidationError(
                f"Обнаружены невалидные каналы: {sorted(invalid_channels)}. "
                f"Доступные каналы: {sorted(valid_channels)}."
            )
        return value

    def validate(self, attrs: dict) -> dict:
        """
        Валидация на уровне объекта.

        Проверяет существование пользователей и заменяет список ID
        на объекты User для оптимизации запросов к базе данных.

        Args:
            attrs: Атрибуты для валидации

        Returns:
            dict: Валидированные атрибуты с объектами User вместо ID

        Raises:
            ValidationError: Если список пользователей пуст или содержатся несуществующие ID
        """

        user_ids = attrs.get("users", [])

        if not user_ids:
            raise serializers.ValidationError("user_ids is empty/")
        users = User.objects.filter(id__in=user_ids)
        existing_ids = {user.id for user in users}
        non_existing_ids = set(user_ids) - existing_ids

        if non_existing_ids:
            raise serializers.ValidationError(
                {"user_ids": f"Users with IDs {sorted(non_existing_ids)} not found"}
            )

        attrs["users"] = users
        return attrs

    def create(self, validated_data) -> MassNotification:
        """
        Создание массовой рассылки и связей с получателями.

        Использует bulk_create для эффективного создания связей
        через промежуточную модель NotificationRecipient.

        Args:
            validated_data: Валидированные данные для создания рассылки

        Returns:
            MassNotification: Созданный объект массовой рассылки
        """

        users = validated_data.pop("users", [])
        notification = MassNotification.objects.create(**validated_data)
        notification_recipients = [
            NotificationRecipient(notification=notification, user=user)
            for user in users
        ]

        NotificationRecipient.objects.bulk_create(notification_recipients)

        notification.total_recipients = len(notification_recipients)
        notification.save()

        return notification
