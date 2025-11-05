# core/celery.py


import os
from celery import Celery


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Create Celery application instance.
app = Celery('core')

# Load configuration from your settings.py (using the CELERY_ prefix).
app.config_from_object('django.conf:settings', namespace='CELERY')

#
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
