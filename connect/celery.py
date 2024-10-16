from __future__ import absolute_import, unicode_literals
import os
import sys

from celery import Celery, schedules

from connect import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "connect.settings")

app = Celery("connect")
app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

task_create_missing_queues = True

# Billing Tasks

app.conf.task_routes = {
    "sync_contacts": {"queue": "billing"},
    "count_contacts": {"queue": "billing"},
    "retry_billing_tasks": {"queue": "billing"},
    "create_contacts": {"queue": "billing"},
    "end_trial_plan": {"queue": "billing"},
    "daily_contact_count": {"queue": "billing"},
    "sync_total_contact_count": {"queue": "sync"},
}


app.conf.beat_schedule = {
    "delete-status-logs": {
        "task": "connect.common.tasks.delete_status_logs",
        "schedule": schedules.crontab(hour="22", minute=0),
    },
    "check-organization-free-plan": {
        "task": "connect.common.tasks.check_organization_free_plan",
        "schedule": schedules.crontab(minute="*/6"),
    },
    "sync_total_contact_count": {
        "task": "connect.common.tasks.sync_total_contact_count",
        "schedule": schedules.crontab(hour="3", minute=0),
    },
    "capture_invoice": {
        "task": "connect.common.tasks.capture_invoice",
        "schedule": schedules.crontab(hour="8,10,13,15,17", minute=0),
    },
    # "sync_contacts": {
    #     "task": "sync_contacts",
    #     "schedule": schedules.crontab(hour=settings.SYNC_CONTACTS_SCHEDULE, minute=0)
    # },
    # "sync-repositories-statistics": {
    #     "task": "connect.common.tasks.sync_repositories_statistics",
    #     "schedule": schedules.crontab(minute="*/8")
    # },
    "count_contacts": {
        "task": "count_contacts",
        "schedule": schedules.crontab(hour="*/6", minute=0),
    },
    "retry_billing_tasks": {
        "task": "retry_billing_tasks",
        "schedule": schedules.crontab(hour="1"),
    },
    "problem_capture_invoice": {
        "task": "problem_capture_invoice",
        "schedule": schedules.crontab(hour="9,11,14,16,18", minute=0),
    },
    "daily_contact_count": {
        "task": "daily_contact_count",
        "schedule": schedules.crontab(hour="23", minute=59),
    },
    "end_trial_plan": {
        "task": "end_trial_plan",
        "schedule": schedules.crontab(hour="20", minute=0),
    },
    "keycloak_logs_cleanup_routine": {
        "task": "keycloak_logs_cleanup_routine",
        "schedule": schedules.crontab(hour="23", minute=30),
    },
    "recent_activity_cleanup_routine": {
        "task": "delete_recent_activities",
        "schedule": schedules.crontab(hour="23", minute=0),
    },
}

if "test" in sys.argv or getattr(settings, "CELERY_ALWAYS_EAGER", False):
    from celery import current_app

    def send_task(name, args=(), kwargs={}, **opts):  # pragma: needs cover
        task = current_app.tasks[name]
        return task.apply(args, kwargs, **opts)

    current_app.send_task = send_task
