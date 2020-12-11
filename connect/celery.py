from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

from connect import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "connect.settings")

app = Celery("connect")
app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

app.conf.beat_schedule = {
    "check-status-services": {
        "task": "connect.common.tasks.status_service",
        "schedule": 5.0,
    },
}


@app.task(bind=True)
def debug_task(self):
    print("Request: {0!r}".format(self.request))
