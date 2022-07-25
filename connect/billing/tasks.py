import stripe
import pendulum
from connect.celery import app
from connect.common.models import Organization, Project, BillingPlan
from connect.billing.models import Contact, Message, SyncManagerTask, ContactCount, Channel
from connect.elastic.flow import ElasticFlow
from datetime import timedelta
from django.utils import timezone
from connect import utils
from celery import current_app
from grpc._channel import _InactiveRpcError
from django.conf import settings


@app.task(
    name="get_messages",
    autoretry_for=(_InactiveRpcError, Exception),
    retry_kwargs={"max_retries": 5},
    retry_backoff=True,
)
def get_messages(contact_uuid: str, before: str, after: str, project_uuid: str):

    flow_instance = utils.get_grpc_types().get("flow")
    contact = Contact.objects.get(uuid=contact_uuid)
    project = Project.objects.get(uuid=project_uuid)
    message = flow_instance.get_message(str(project.flow_organization), str(contact.contact_flow_uuid), before, after)

    if len(message.uuid) == 0:
        return False
    try:
        Message.objects.get(message_flow_uuid=message.uuid)
    except Message.DoesNotExist:
        Message.objects.create(
            contact=contact,
            text=message.text,
            created_on=message.created_on,
            direction=message.direction,
            message_flow_uuid=message.uuid
        )

    channel = Channel.create(
        channel_type=message.channel_type,
        channel_flow_id=message.channel_id,
        project=project
    )
    contact.update_channel(channel)
    return True


@app.task(name="sync_contacts")
def sync_contacts(sync_before: str = None, sync_after: str = None):
    if sync_before and sync_after:
        sync_before = pendulum.parse(sync_before)
        sync_after = pendulum.parse(sync_after)
        manager = SyncManagerTask.objects.create(
            task_type="sync_contacts",
            started_at=timezone.now(),
            before=sync_before,
            after=sync_after
        )
    else:

        last_sync = (
            SyncManagerTask.objects.filter(task_type="sync_contacts")
            .order_by("finished_at")
            .last()
        )
        manager = SyncManagerTask.objects.create(
            task_type="sync_contacts",
            started_at=timezone.now(),
            before=timezone.now(),
            after=last_sync.before
            if isinstance(last_sync, SyncManagerTask)
            else timezone.now() - timedelta(hours=5),
        )

    try:
        elastic_instance = ElasticFlow()
        update_fields = ["finished_at", "status"]
        for project in Project.objects.exclude(flow_id=None):
            active_contacts = list(elastic_instance.get_contact_detailed(
                str(project.flow_id), str(manager.before), str(manager.after)
            ))
            for elastic_contact in active_contacts:
                contact = Contact.objects.create(
                    contact_flow_uuid=elastic_contact.uuid,
                    name=elastic_contact.name,
                    last_seen_on=pendulum.parse(elastic_contact.last_seen_on),
                )
                has_message = get_messages(str(contact.uuid), str(manager.before), str(manager.after), str(project.uuid))
                if not has_message:
                    last_message = Message.objects.filter(
                        contact=contact,
                        created_on__date__month=timezone.now().date().month,
                        created_on__date__year=timezone.now().date().year
                    )
                    if not last_message.exists():
                        contact.delete()
                        manager.fail_message = "Contact don't have delivery/received message"
                        update_fields.append('fail_message')
                
        count_contacts.delay(manager.before, manager.after)

        manager.finished_at = timezone.now()
        manager.status = True
        manager.save(update_fields=update_fields)
        return manager.status
    except Exception as error:
        manager.finished_at = timezone.now()
        manager.fail_message = str(error)
        manager.status = False
        manager.save(update_fields=["finished_at", "status", "fail_message"])
        return False


@app.task(name="retry_billing_tasks")
def retry_billing_tasks():
    task_failed = SyncManagerTask.objects.filter(status=False, retried=False)

    for task in task_failed:
        task.retried = True
        task.save()
        if task.task_type == 'count_contacts':
            current_app.send_task(  # pragma: no cover
                name="count_contacts",
                args=[task.before, task.after]
            )

        elif task.task_type == 'sync_contacts':
            current_app.send_task(  # pragma: no cover
                name="sync_contacts",
                args=[task.before, task.after]
            )

    return True


@app.task(name="count_contacts")
def count_contacts(before, after):
    manager = SyncManagerTask.objects.create(
            task_type="count_contacts",
            started_at=pendulum.now(),
            before=before,
            after=after
        )
    try:
        for project in Project.objects.all():
            for channel in project.channel.all():
                amount = Contact.objects.filter(channel=channel, last_seen_on__range=(after, before)) 
                try:
                    contact_count = ContactCount.objects.get(channel=channel, created_at__range=(after, before))
                except ContactCount.DoesNotExist:
                    contact_count = ContactCount.objects.create(channel=channel, count=0)
                contact_count.increase_contact_count(amount)
            manager.status = True
            manager.finished_at=pendulum.now()
            manager.save(update_fields=["status", "finished_at"])
    except Exception as error:
        manager.finished_at = pendulum.now()
        manager.fail_message = str(error)
        manager.status = False
        manager.save(update_fields=["finished_at", "status", "fail_message"])
        return False



@app.task(name="refund_validation_charge")
def refund_validation_charge(charge_id):  # pragma: no cover
    stripe.api_key = settings.BILLING_SETTINGS.get("stripe", {}).get("API_KEY")
    stripe.Refund.create(charge=charge_id)
    return True


@app.task(name="problem_capture_invoice")
def problem_capture_invoice():
    for organization in Organization.objects.filter(organization_billing__plan=BillingPlan.PLAN_ENTERPRISE, is_suspended=False):
        if organization.organization_billing.problem_capture_invoice:
            organization.is_suspended = True
            organization.save(update_fields=["is_suspended"])
            organization.organization_billing.is_active = False
            organization.organization_billing.save(update_fields=["is_active"])
            for project in organization.project.all():
                current_app.send_task(  # pragma: no cover
                    name="update_suspend_project",
                    args=[project.flow_organization, True]
                )
