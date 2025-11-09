import pytest
from django.core.exceptions import ValidationError

from .factories import UserContactFactory, UserFactory


@pytest.mark.django_db
class TestUserContactModel:
    """Тесты модели UserContact: валидация телефона, уникальность полей и связь с User."""

    def test_str_representation(self):
        """Тест строкового представления модели."""
        user = UserFactory(username="testuser")
        contact = UserContactFactory(user=user, phone_number="+79991234567")
        expected_str = "Контакты пользователя testuser"
        assert str(contact) == expected_str

    def test_unique_phone_number(self):
        """Тест уникальности номера телефона."""
        UserContactFactory(phone_number="+79991234567")
        with pytest.raises(ValidationError):
            UserContactFactory(phone_number="+79991234567")

    def test_unique_telegram_profile(self):
        """Тест уникальности профиля Telegram."""
        UserContactFactory(telegram_profile="https://t.me/user1")
        with pytest.raises(ValidationError):
            UserContactFactory(telegram_profile="https://t.me/user1")

    def test_one_to_one_user_link(self):
        """Тест связи один-к-одному с User."""
        user = UserFactory()
        UserContactFactory(user=user)
        with pytest.raises(ValidationError):
            UserContactFactory(user=user)

    def test_clean_valid_phone_plus7(self):
        """Тест валидации и очистки номера телефона (+7)."""
        contact = UserContactFactory.build(phone_number="+79991234567")
        contact.clean()
        assert contact.phone_number == "+79991234567"

    def test_clean_valid_phone_8(self):
        """Тест валидации и очистки номера телефона (8)."""
        contact = UserContactFactory.build(phone_number="89991234567")
        contact.clean()
        assert contact.phone_number == "+79991234567"

    def test_clean_valid_phone_with_spaces_and_symbols(self):
        """Тест валидации и очистки номера с пробелами и скобками."""
        contact = UserContactFactory.build(phone_number="+7 (999) 123-45-67")
        contact.clean()
        assert contact.phone_number == "+79991234567"

    def test_clean_invalid_phone_format(self):
        """Тест валидации неверного формата номера телефона."""
        contact = UserContactFactory.build(phone_number="123456")
        with pytest.raises(ValidationError) as exc_info:
            contact.clean()
        assert "phone_number" in exc_info.value.error_dict
        assert "Неверный формат номера телефона" in str(exc_info.value)

    def test_clean_invalid_phone_too_short(self):
        """Тест валидации слишком короткого номера телефона."""
        contact = UserContactFactory.build(phone_number="+799912345")
        with pytest.raises(ValidationError) as exc_info:
            contact.clean()
        assert "phone_number" in exc_info.value.error_dict

    def test_clean_invalid_phone_too_long(self):
        """Тест валидации слишком длинного номера телефона."""
        contact = UserContactFactory.build(phone_number="+799912345678")
        with pytest.raises(ValidationError) as exc_info:
            contact.clean()
        assert "phone_number" in exc_info.value.error_dict

    def test_save_calls_clean(self):
        """Тест, что метод save вызывает clean/full_clean."""
        contact = UserContactFactory.build(phone_number="invalid_number")
        with pytest.raises(ValidationError):
            contact.save()

    def test_save_normalizes_phone_number(self):
        """Тест, что save нормализует номер при сохранении."""
        user = UserFactory()
        contact = UserContactFactory.build(user=user, phone_number="8 (999) 123-45-67")
        contact.save()
        assert contact.phone_number == "+79991234567"

    def test_blank_null_fields(self):
        """Тест, что поля могут быть пустыми (blank=True, null=True)."""
        contact = UserContactFactory(phone_number=None, telegram_profile=None)
        assert contact.phone_number is None
        assert contact.telegram_profile is None

    def test_related_name_access(self):
        """Тест доступа к контакту через related_name у User."""
        user = UserFactory()
        contact = UserContactFactory(user=user)
        assert user.contact == contact
