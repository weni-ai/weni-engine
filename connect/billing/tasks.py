import stripe
import pendulum
from connect.celery import app
from connect.common.models import Organization, Project, BillingPlan
from connect.billing.models import (
    Contact,
    Message,
    SyncManagerTask,
    ContactCount,
    Channel,
)
from connect.elastic.flow import ElasticFlow
from django.utils import timezone
from connect import utils
from celery import current_app
from django.conf import settings


@app.task(
    name="get_messages",
    ignore_result=True
)
def get_messages(temp_channel_uuid: str, before: str, after: str, project_uuid: str):
    manager = SyncManagerTask.objects.create(
        task_type="get_messages",
        started_at=pendulum.now(),
        before=pendulum.parse(before),
        after=pendulum.parse(after)
    )

    flow_instance = utils.get_grpc_types().get("flow")
    project = Project.objects.get(uuid=project_uuid)
    contacts = Contact.objects.filter(channel__uuid=temp_channel_uuid, last_seen_on__range=(after, before))
    for contact in contacts:
        message = flow_instance.get_message(
            str(project.flow_organization), str(contact.contact_flow_uuid), before, after
        )

        if not message:
            last_message = Message.objects.filter(
                contact=contact,
                created_on__date__month=timezone.now().date().month,
                created_on__date__year=timezone.now().date().year,
            )

        if not last_message.exists():
            contact.delete()
            manager.fail_message.create(
                message="Contact don't have delivery/received message"
            )

            continue

        try:
            Message.objects.get(message_flow_uuid=message.uuid)
        except Message.DoesNotExist:
            Message.objects.create(
                contact=contact,
                text=message.text,
                created_on=message.created_on,
                direction=message.direction,
                message_flow_uuid=message.uuid,
            )

        channel = Channel.create(
            channel_type=message.channel_type,
            channel_flow_id=message.channel_id,
            project=project,
        )
        contact.update_channel(channel)

    count_contacts.apply_async(args=[manager.before, manager.after, project_uuid])

    return True


@app.task(name="create_contacts", ignore_result=True)
def create_contacts(active_contacts: list, project_uuid: Project):

    project = Project.objects.get(uuid=project_uuid)
    contacts_to_save = list()
    for elastic_contact in active_contacts:
        contacts_to_save.append(
            Contact(
                contact_flow_uuid=elastic_contact["_source"].get("uuid"),
                name=elastic_contact["_source"].get("name"),
                last_seen_on=pendulum.parse(elastic_contact["_source"].get("last_seen_on")),
                project=project
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
                    str(project.flow_id), str(manager.before), str(manager.after), scroll_id=scroll["scroll_id"]
                )
                if scrolled == scroll["scroll_size"]:
                    break

            count_contacts.apply_async(args=[manager.before, manager.after, project.uuid])

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

        if task.task_type == "sync_contacts":
            current_app.send_task(  # pragma: no cover
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
        amount = project.contacts.filter(last_seen_on__range=(after, before)).distinct("contact_flow_uuid").count()
        now = pendulum.now()
        try:
            contact_count = ContactCount.objects.get(
                created_at__range=(now.start_of("day"), now.end_of("day")), project=project
            )
        except ContactCount.DoesNotExist:
            contact_count = ContactCount.objects.create(
                project=project,
                count=0
            )

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
    for organization in Organization.objects.filter(
        organization_billing__plan=BillingPlan.PLAN_ENTERPRISE, is_suspended=False
    ):
        if organization.organization_billing.problem_capture_invoice:
            organization.is_suspended = True
            organization.save(update_fields=["is_suspended"])
            organization.organization_billing.is_active = False
            organization.organization_billing.save(update_fields=["is_active"])
            for project in organization.project.all():
                current_app.send_task(  # pragma: no cover
                    name="update_suspend_project",
                    args=[project.flow_organization, True],
                )


@app.task(name="end_trial_plan")
def end_trial_plan():
    yesterday = pendulum.yesterday()
    for organization in Organization.objects.filter(organization_billing__plan=BillingPlan.PLAN_TRIAL,
                                                    organization_billing__trial_end_date__date=yesterday.date()):
        organization.organization_billing.end_trial_period()
        organization.organization_billing.send_email_trial_plan_expired_due_time_limit()


@app.task(name="check_organization_plans")
def check_organization_plans():
    # utc-3 or project_timezone

    for organization in Organization.objects.filter(is_suspended=False).exclude(organization_billing__plan__in=[
            BillingPlan.PLAN_TRIAL, BillingPlan.PLAN_CUSTOM, BillingPlan.PLAN_ENTERPRISE]):

        next_due_date = pendulum.parse(str(organization.organization_billing.next_due_date))
        after = next_due_date.subtract(months=1).strftime("%Y-%m-%d %H:%M")
        before = next_due_date.strftime("%Y-%m-%d %H:%M")
        for project in organization.project.all():
            contact_count = utils.count_contacts(
                project=project, before=before, after=after
            )
            project.contact_count = int(contact_count)
            project.save(update_fields=["contact_count"])

        current_active_contacts = organization.active_contacts

        if current_active_contacts > organization.organization_billing.plan_limit:
            organization.organization_billing.end_trial_period()

            organization.organization_billing.send_email_plan_expired_due_attendance_limit()

        elif current_active_contacts > organization.organization_billing.plan_limit - 50:
            organization.organization_billing.send_email_plan_is_about_to_expire()

    return True
