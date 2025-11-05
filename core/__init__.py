# core/__init__.py
from .celery import app as celery_app

# This ensures the celery app is always imported when Django starts,
# so that shared_task will work.
__all__ = ('celery_app',)