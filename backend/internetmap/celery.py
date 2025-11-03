import os
from celery import Celery


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'internetmap.settings')

app = Celery('internetmap')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
