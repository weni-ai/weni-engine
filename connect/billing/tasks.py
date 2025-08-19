import stripe
import pendulum
from connect.celery import app
from connect.common.models import (
    Organization,
    Project,
    BillingPlan,
)
from connect.billing.models import (
    Contact,
    SyncManagerTask,
    ContactCount,
)
from connect.elastic.flow import ElasticFlow
from django.utils import timezone
from celery import current_app
from django.conf import settings


@app.task(name="create_contacts", ignore_result=True)
def create_contacts(active_contacts: list, project_uuid: Project):

    project = Project.objects.get(uuid=project_uuid)
    contacts_to_save = list()
    for elastic_contact in active_contacts:
        contacts_to_save.append(
            Contact(
                contact_flow_uuid=elastic_contact["_source"].get("uuid"),
                name=elastic_contact["_source"].get("name"),
                last_seen_on=pendulum.parse(
                    elastic_contact["_source"].get("last_seen_on")
                ),
                project=project,
            )
        )
    Contact.objects.bulk_create(contacts_to_save)


@app.task(name="sync_contacts", ignore_result=True)
def sync_contacts(
    sync_before: str = None, sync_after: str = None, task_uuid: str = None
):
    if sync_before and sync_after:
        sync_before = pendulum.parse(sync_before)
        sync_after = pendulum.parse(sync_after)
        manager = SyncManagerTask.objects.get(uuid=task_uuid)
    else:
        manager = SyncManagerTask.objects.create(
            task_type="sync_contacts",
            started_at=pendulum.now(),
            before=pendulum.now(),
            after=pendulum.now().subtract(hours=1),
        )

    try:
        elastic_instance = ElasticFlow()
        update_fields = ["finished_at", "status"]
        projects = Project.objects.exclude(flow_id=None)
        scroll = {}
        for project in projects:
            if scroll != {}:
                elastic_instance.clear_scroll(scroll_id=scroll["scroll_id"])
            scroll, active_contacts = list(
                elastic_instance.get_paginated_contacts(
                    str(project.flow_id), str(manager.before), str(manager.after)
                )
            )

            scrolled = 0

            while scrolled <= scroll["scroll_size"]:
                scrolled += len(active_contacts)

                create_contacts.apply_async(args=[active_contacts, str(project.uuid)])
                active_contacts = elastic_instance.get_paginated_contacts(
                    str(project.flow_id),
                    str(manager.before),
                    str(manager.after),
                    scroll_id=scroll["scroll_id"],
                )
                if scrolled == scroll["scroll_size"]:
                    break

            count_contacts.apply_async(
                args=[manager.before, manager.after, project.uuid]
            )

        manager.finished_at = timezone.now()
        manager.status = True
        manager.save(update_fields=update_fields)
        return manager.status
    except Exception as error:
        manager.finished_at = timezone.now()
        manager.fail_message.create(message=str(error))
        manager.status = False
        manager.save(update_fields=["finished_at", "status"])
        return False


@app.task(name="retry_billing_tasks")
def retry_billing_tasks():
    task_failed = SyncManagerTask.objects.filter(status=False, retried=False)

    for task in task_failed:
        task.retried = True
        task.save()

        if task.task_type == "sync_contacts":  # pragma: no cover
            current_app.send_task(
                name="sync_contacts", args=[task.before, task.after, task.uuid]
            )

    return True


@app.task(name="count_contacts", ignore_result=True)
def count_contacts(before, after, project_uuid: str, task_uuid: str = None):
    if task_uuid:
        manager = SyncManagerTask.objects.get(uuid=task_uuid)
    else:
        manager = SyncManagerTask.objects.create(
            task_type="count_contacts",
            started_at=pendulum.now(),
            before=before,
            after=after,
        )
    try:
        project = Project.objects.get(uuid=project_uuid)
        amount = (
            project.contacts.filter(last_seen_on__range=(after, before))
            .distinct("contact_flow_uuid")
            .count()
        )
        now = pendulum.now()
        try:
            contact_count = ContactCount.objects.get(
                created_at__range=(now.start_of("day"), now.end_of("day")),
                project=project,
            )
        except ContactCount.DoesNotExist:
            contact_count = ContactCount.objects.create(project=project, count=0)

        contact_count.increase_contact_count(amount)
        manager.status = True
        manager.finished_at = pendulum.now()
        manager.save(update_fields=["status", "finished_at"])
        return True
    except Exception as error:
        manager.finished_at = pendulum.now()
        manager.fail_message.create(message=str(error))
        manager.status = False
        manager.save(update_fields=["finished_at", "status"])
        return False


@app.task(name="refund_validation_charge")
def refund_validation_charge(charge_id):  # pragma: no cover
    stripe.api_key = settings.BILLING_SETTINGS.get("stripe", {}).get("API_KEY")
    stripe.Refund.create(charge=charge_id)
    return True


@app.task(name="problem_capture_invoice")
def problem_capture_invoice():
    plan_list = [
        BillingPlan.PLAN_START,
        BillingPlan.PLAN_SCALE,
        BillingPlan.PLAN_ADVANCED,
    ]

    organizations = organizations = Organization.objects.filter(
        organization_billing__plan__in=plan_list, is_suspended=False
    )

    for organization in organizations:
        if organization.organization_billing.problem_capture_invoice:
            organization.is_suspended = True
            organization.save(update_fields=["is_suspended"])
            organization.organization_billing.is_active = False
            organization.organization_billing.save(update_fields=["is_active"])
            for project in organization.project.all():
                current_app.send_task(  # pragma: no cover
                    name="update_suspend_project",
                    args=[project.uuid, True],
                )


@app.task(name="end_trial_plan")
def end_trial_plan():
    yesterday = pendulum.yesterday()
    # End first trial period for orgs that haven't enabled the extension
    for organization in Organization.objects.filter(
        organization_billing__plan=BillingPlan.PLAN_TRIAL,
        organization_billing__trial_extension_enabled=False,
        organization_billing__trial_end_date__date=yesterday.date(),
    ):
        organization.organization_billing.end_trial_period()
        organization.organization_billing.send_email_trial_plan_expired_due_time_limit()

    # End second trial period (extension)
    for organization in Organization.objects.filter(
        organization_billing__plan=BillingPlan.PLAN_TRIAL,
        organization_billing__trial_extension_enabled=True,
        organization_billing__trial_extension_end_date__date=yesterday.date(),
    ):
        organization.organization_billing.end_trial_period()
        organization.organization_billing.send_email_trial_plan_expired_due_time_limit()


@app.task(name="daily_contact_count")
def daily_contact_count():
    """Daily contacts"""
    today = pendulum.now().end_of("day")

    for project in Project.objects.all():
        after = today.start_of("day")
        before = today
        total_day_calls = (
            Contact.objects.filter(project=project)
            .filter(last_seen_on__range=(after, before))
            .distinct("contact_flow_uuid")
            .count()
        )
        cc, created = ContactCount.objects.get_or_create(
            project=project, day=after, defaults={"count": total_day_calls}
        )
