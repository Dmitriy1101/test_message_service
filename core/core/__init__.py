"""
Подключаем Celery к проекту.
"""

from celery_app import app as celery_app

__all__ = ("celery_app",)
