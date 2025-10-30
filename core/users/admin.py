from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.models import User
from .models import UserContact


class UserContactInline(admin.StackedInline):
    """
    Inline-модель для отображения UserContact внутри админки User.
    """

    model = UserContact
    can_delete = False
    verbose_name_plural = "Контактная информация"


class CustomUserCreationForm(UserCreationForm):
    """
    Кастомная форма создания пользователя.
    """

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name")


class CustomUserAdmin(UserAdmin):
    """
    Расширенная админка, добавляющая контакты.
    """

    inlines = [UserContactInline]
    list_display = [
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_superuser",
        "get_phone_number",
    ]
    list_filter = ["is_staff", "is_superuser", "is_active", "groups"]
    search_fields = ["username", "email", "contact__phone_number"]
    list_select_related = True
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", "password1", "password2"),
            },
        ),
    )

    def get_queryset(self, request):
        """
        Оптимизация запросов - предзагрузка контактов.
        """
        queryset = super().get_queryset(request)
        return queryset.prefetch_related("contact")

    def get_phone_number(self, obj: User) -> str:
        """
        Кастомный метод для отображения номера телефона в списке пользователей.

        Args:
            obj: Экземпляр модели User

        Returns:
            str: Номер телефона или "-" если не указан
        """
        return (
            obj.contact.phone_number
            if hasattr(obj, "contact") and obj.contact.phone_number
            else "-"
        )

    def get_telegram_profile(self, obj: User) -> str:
        """
        Отображает Telegram профиль в списке пользователей.
        """
        if hasattr(obj, "contact") and obj.contact.telegram_profile:
            telegram_url = obj.contact.telegram_profile
            if "t.me/" in telegram_url:
                return telegram_url.split("t.me/")[-1]
            return telegram_url
        return "—"

    get_phone_number.short_description = "Телефон"
    get_phone_number.admin_order_field = "contact__phone_number"
    get_telegram_profile.short_description = "Telegram"
    get_telegram_profile.admin_order_field = "contact__telegram_profile"


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(UserContact)
class UserContactAdmin(admin.ModelAdmin):
    """Отдельная админка для управления контактами."""

    list_display = [
        "user",
        "user_email",
        "phone_number",
        "telegram_short",
        "user_is_staff",
        "user_is_active",
    ]
    list_filter = ["user__is_staff", "user__is_superuser", "user__is_active"]
    search_fields = [
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
        "phone_number",
    ]
    raw_id_fields = ["user"]
    list_per_page = 50
    autocomplete_fields = ["user"]

    def get_queryset(self, request):
        """
        Оптимизация запросов с select_related.
        """
        return super().get_queryset(request).select_related("user")

    def user_is_staff(self, obj):
        """Статус staff пользователя."""
        return obj.user.is_staff

    def user_is_active(self, obj):
        """Активности пользователя."""
        return obj.user.is_active

    def user_email(self, obj):
        """email пользователя."""
        return obj.user.email

    def telegram_short(self, obj):
        """Telegram профиля."""
        if obj.telegram_profile:
            url = obj.telegram_profile
            return url
        return "—"

    user_is_staff.short_description = "Staff"
    user_is_staff.boolean = True
    user_is_active.short_description = "Active"
    user_is_active.boolean = True
    user_email.short_description = "Email"
    user_email.admin_order_field = "user__email"
    telegram_short.short_description = "Telegram"
