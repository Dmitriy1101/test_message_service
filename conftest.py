import pytest
from django.test import override_settings


@pytest.fixture(autouse=True, scope="session")
def use_test_settings():
    """
    Фикстура, которая автоматически применяет настройки для тестов
    ко всей сессии pytest.
    """
    with override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            }
        }
    ):
        yield
