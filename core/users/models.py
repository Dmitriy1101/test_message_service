import re

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models


class UserContact(models.Model):
    """
    Модель для хранения контактной информации пользователей.

    Attributes:
        user (OneToOneField): Связь с моделью User один-к-одному
        phone_number (CharField): Номер телефона пользователя
        telegram_profile (URLField): Ссылка на профиль Telegram
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="contact")
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Номер телефона",
        unique=True,
        help_text="Формат: +79991234567 или 89991234567",
    )
    telegram_profile = models.URLField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Профиль Telegram",
        unique=True,
        help_text="Ссылка на профиль Telegram (https://t.me/username)",
    )

    def __str__(self) -> str:
        return f"Контакты пользователя {self.user.username}"

    class Meta:
        verbose_name = "Контакт пользователя"
        verbose_name_plural = "Контакты пользователей"
        db_table = "user_contacts"

    def clean(self):
        """
        Валидация данных модели перед сохранением.

        Raises:
            ValidationError: Если номер телефона имеет неверный формат
        """
        super().clean()

        if self.phone_number:
            cleaned_phone: str = re.sub(r"[\s\(\)\-]", "", self.phone_number)
            if not re.match(r"^(\+7|8)\d{10}$", cleaned_phone):
                raise ValidationError(
                    {
                        "phone_number": "Неверный формат номера телефона.\
                            Используйте: +79991234567 или 89991234567"
                    }
                )

            self.phone_number: str = f"+7{cleaned_phone[-10:]}"

    def save(self, *args, **kwargs) -> None:
        """
        Добавлена валидация перед сохранением
        """

        self.full_clean()
        super().save(*args, **kwargs)
