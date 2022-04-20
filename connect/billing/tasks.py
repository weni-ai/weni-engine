from connect.celery import app
from connect import utils
from connect.common.models import Project
from connect.billing.models import Channel, Contact, Message, SyncManagerTask
from datetime import datetime, timedelta
from django.utils import timezone


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
        if last_sync.exists()
        else timezone.now() - timedelta(hours=5),
    )
    try:
        grpc_instance = utils.get_grpc_types().get("flow")

        for project in Project.objects.all():
            active_contacts = grpc_instance.get_active_contacts(
                str(project.flow_organization), manager.before, manager.after
            )
            for contact in active_contacts:
                channel = Channel.create(
                    project=project,
                    channel_flow_uuid=contact.channel.uuid,
                    channel_type="WA",
                    name=contact.channel.name,
                )
                new_contact = Contact.objects.create(
                    contact_flow_uuid=contact.uuid,
                    name=contact.name,
                    channel=channel,
                )
                Message.objects.get_or_create(
                    contact=new_contact,
                    text=contact.msg.text,
                    sent_on=datetime.fromtimestamp(contact.msg.sent_on.seconds),
                    message_flow_uuid=contact.msg.uuid,
                )

        manager.finished_at = timezone.now()
        manager.status = True
        manager.save(update_fields=["finished_at", "status"])
    except Exception:
        manager.finished_at = timezone.now()
        manager.status = False
        manager.save(update_fields=["finished_at", "status"])


@app_task()
def retry_billing_tasks():
    task_failed = SyncManagerTask.objects.filter(status=False, retried=False)

    for task in task_failed:
        status = False
        task.retried = True
        task.save()
        if task.task_type == 'count_contacts':
            status = count_contacts().delay()
        elif task.task_type == 'sync_contacts':
            # status = sync_contacts().delay()
            status = True
        return status


@app_task()
def count_contacts():
    last_sync = SyncManagerTask.objects.filter(task_type="sync_contacts").order_by("finished_at").last()
    manager = SyncManagerTask.objects.create(
        task_type="count_contacts",
        started_at=timezone.now(),
        before=timezone.now(),
        after=last_sync.before if last_sync.exists() else timezone.now() - timedelta(hours=5)
    )
    days = {}
    for contact in Contact.objects.filter(created_at__lte=last_sync.before, created_at__gte=last_sync.after):
        contact_count = ContactCount.objects.filter(
            created_at__day=contact.created_at.day,
            created_at__month=contact.created_at.month,
            created_at__year=contact.created_at.year,
            channel=contact.channel
        )
        cur_date = contact.created_at.day + "-" + contact.created_at.month + "-" + contact.created_at.year + '-' + contact.channel.channel_flow_uuid
        days[cur_date] = 1 if not contact_count.exists() else days[cur_date] + 1
    for day, count in days.items():
        cur_day = day.split('-')
        contact_count = ContactCount.objects.filter(
            created_at__day=cur_day[0],
            created_at__month=cur_day[1],
            created_at__year=cur_day[2],
            channel__channel_flow_uuid=cur_date[3]
        )
        if contact_count.exists():
            contact_count = contact_count.first()
            contact_count.increase_contact_count(count)
        else:
            ContactCount.objects.create(
                channel=Chanel.objects.get(channel_flow_uuid=cur_date[3]),
                count=count
            )