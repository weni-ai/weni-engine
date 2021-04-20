from __future__ import absolute_import, unicode_literals
import os
import sys

from celery import Celery

from weni import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "weni.settings")

app = Celery("weni")
app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

app.conf.beat_schedule = {
    "check-status-services": {
        "task": "weni.common.tasks.status_service",
        "schedule": 10.0,
    },
    "sync-project-flows-organization-info": {
        "task": "weni.common.tasks.sync_updates_projects",
        "schedule": 30.0,
    },
}


@app.task(bind=True)
def debug_task(self):
    print("Request: {0!r}".format(self.request))


if "test" in sys.argv or getattr(settings, "CELERY_ALWAYS_EAGER", False):
    from celery import current_app

    def send_task(name, args=(), kwargs={}, **opts):  # pragma: needs cover
        task = current_app.tasks[name]
        return task.apply(args, kwargs, **opts)

    current_app.send_task = send_task
