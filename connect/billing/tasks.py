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
