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
    message = flow_instance.get_message(project.flow_organization, contact.contact_flow_uuid, before, after)

    Message.objects.create(
        contact=contact,
        text=message.text,
        created_on=message.created_on,
        direction=message.direction,
        message_flow_uuid=message.message_flow_uuid
    )

    channel = Channel.create(
        channel_type=message.channel_type,
        channel_flow_id=message.channel_id,
        project=project
    )
    contact.update_channel(channel)


@app.task()
def sync_contacts():
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

        for project in Project.objects.all():
            active_contacts = elastic_instance.get_contact_detailed(
                str(project.flow_id), str(manager.before), str(manager.after)
            )
            for elastic_contact in active_contacts:
                contact = Contact.objects.create(
                    contact_flow_uuid=elastic_contact.uuid,
                    name=elastic_contact.name,
                    last_seen_on=pendulum.parse(elastic_contact.last_seen_on),
                )

                task = current_app.send_task(  # pragma: no cover
                    name="get_messages",
                    args=[contact.uuid, str(manager.before), str(manager.after), project.uuid],
                )
                task.wait()

        manager.finished_at = timezone.now()
        manager.status = True
        manager.save(update_fields=["finished_at", "status"])
        return True
    except Exception as error:
        manager.finished_at = timezone.now()
        manager.fail_message = str(error)
        manager.status = False
        manager.save(update_fields=["finished_at", "status", "fail_message"])
        return False


@app.task()
def retry_billing_tasks():
    task_failed = SyncManagerTask.objects.filter(status=False, retried=False)

    for task in task_failed:
        status = False
        task.retried = True
        task.save()
        if task.task_type == 'count_contacts':
            task = current_app.send_task(  # pragma: no cover
                name="count_contacts",
            )
            task.wait()
        elif task.task_type == 'sync_contacts':
            task = current_app.send_task(  # pragma: no cover
                name="sync_contacts",
            )
            task.wait()
        return status


@app.task()
def count_contacts():
    last_sync = SyncManagerTask.objects.filter(task_type="sync_contacts").order_by("finished_at").last()
    manager = SyncManagerTask.objects.create(
        task_type="count_contacts",
        started_at=timezone.now(),
        before=timezone.now(),
        after=last_sync.before if isinstance(last_sync, SyncManagerTask) else timezone.now() - timedelta(hours=5)
    )

    status = False
    days = {}

    for contact in Contact.objects.filter(created_at__lte=last_sync.before, created_at__gte=last_sync.after):
        contact_count = ContactCount.objects.filter(
            created_at__day=contact.created_at.day,
            created_at__month=contact.created_at.month,
            created_at__year=contact.created_at.year,
            channel=contact.channel
        )

        cur_date = f"{contact.created_at.day}-{contact.created_at.month}-{contact.created_at.year}-{contact.channel.uuid}"
        days[cur_date] = 1 if not contact_count.exists() else days[cur_date] + 1

    for day, count in days.items():
        cur_day = day.split('-')
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
