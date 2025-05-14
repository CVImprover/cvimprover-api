# /var/www/html/app/api/cvimprover/celery.py

import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cvimprover.settings')

app = Celery('cvimprover')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
