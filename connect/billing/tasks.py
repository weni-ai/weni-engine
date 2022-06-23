import stripe
import pendulum
from connect.celery import app
from connect.common.models import Project
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
            active_contacts = elastic_instance.get_contact_detailed(
                str(project.flow_id), str(manager.before), str(manager.after)
            )
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
            task = current_app.send_task(  # pragma: no cover
                name="count_contacts",
                args=[task.before, task.after, task.started_at]
            )
            task.wait()
        elif task.task_type == 'sync_contacts':
            task = current_app.send_task(  # pragma: no cover
                name="sync_contacts",
                args=[task.before, task.after]
            )
            task.wait()

    return True


@app.task(name="count_contacts")
def count_contacts(sync_before: str = None, sync_after: str = None, started_at: str = None):
    if sync_before and sync_after and started_at:
        count_before = pendulum.parse(sync_before)
        count_after = pendulum.parse(sync_after)
        count_started_at = pendulum.parse(started_at)

        manager = SyncManagerTask.objects.create(
            task_type="count_contacts",
            started_at=timezone.now(),
            before=count_before,
            after=count_after
        )

        last_sync = SyncManagerTask.objects.filter(
            started_at__gte=count_started_at - timedelta(hours=2),
            started_at__lte=count_started_at,
            task_type="sync_contacts"
        ).last()
    else:
        last_sync = SyncManagerTask.objects.filter(task_type="sync_contacts").order_by("finished_at").last()
        manager = SyncManagerTask.objects.create(
            task_type="count_contacts",
            started_at=timezone.now(),
            before=timezone.now(),
            after=last_sync.before if isinstance(last_sync, SyncManagerTask) else timezone.now() - timedelta(hours=6)
        )

    status = False
    days = {}

    for contact in Contact.objects.filter(created_at__lte=last_sync.finished_at, created_at__gte=last_sync.after):
        contact_count = ContactCount.objects.filter(
            created_at__day=contact.created_at.day,
            created_at__month=contact.created_at.month,
            created_at__year=contact.created_at.year,
            channel=contact.channel
        )

        cur_date = f"{contact.created_at.day}#{contact.created_at.month}#{contact.created_at.year}#{contact.channel.uuid}"
        days[cur_date] = 1 if not contact_count.exists() else days.get(cur_date, 0) + 1

    for day, count in days.items():
        cur_day = day.split('#')
        contact_count = ContactCount.objects.filter(
            created_at__day=cur_day[0],
            created_at__month=cur_day[1],
            created_at__year=cur_day[2],
            channel__uuid=cur_day[3]
        )
        if contact_count.exists():
            contact_count = contact_count.first()
            contact_count.increase_contact_count(count)
            status = True
        else:
            channel = Channel.objects.get(uuid=cur_day[3])
            ContactCount.objects.create(
                count=count,
                channel=channel
            )
            status = True

        manager.status = status
        manager.finished_at = timezone.now()
        manager.save()


@app.task(name="refund_validation_charge")
def refund_validation_charge(charge_id):  # pragma: no cover
    stripe.api_key = settings.BILLING_SETTINGS.get("stripe", {}).get("API_KEY")
    stripe.Refund.create(charge=charge_id)
    return True
