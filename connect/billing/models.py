import logging
import uuid as uuid4
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _


logger = logging.getLogger(__name__)


class FailMessageLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    message = models.TextField()


class SyncManagerTask(models.Model):
    uuid = models.UUIDField(
        _("UUID"), primary_key=True, default=uuid4.uuid4, editable=False
    )
    status = models.BooleanField(
        default=False, help_text=_("Whether this task succeded or not.")
    )
    retried = models.BooleanField(
        default=False, help_text=_("Whether this task retry or not.")
    )
    fail_message = models.ManyToManyField(FailMessageLog, verbose_name=_("Manager fail messages"))
    task_type = models.CharField(_("task type"), max_length=150)
    started_at = models.DateTimeField(_("started at"))
    finished_at = models.DateTimeField(_("finished at"), null=True)
    before = models.DateTimeField(_("before"))
    after = models.DateTimeField(_("after"))


class ContactManager(models.Manager):
    def create(self, *args, **kwargs):
        contact = self.get_contact(kwargs.get("contact_flow_uuid"))
        if contact.exists():
            return contact.first()
        else:
            return super(ContactManager, self).create(*args, **kwargs)

    def get_contact(self, contact_flow_uuid):
        return self.filter(
            created_at__date__month=timezone.now().date().month,
            created_at__date__year=timezone.now().date().year,
            contact_flow_uuid=contact_flow_uuid,
        )


class Contact(models.Model):
    uuid = models.UUIDField(
        _("UUID"), primary_key=True, default=uuid4.uuid4, editable=False
    )
    contact_flow_uuid = models.UUIDField(_("flow identification UUID"))
    name = models.CharField(_("contact name"), max_length=150, blank=True, null=True)
    last_seen_on = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(blank=True, null=True)
    project = models.ForeignKey("common.Project", models.CASCADE, related_name="contacts", null=True)

    objects = ContactManager()


class Message(models.Model):
    uuid = models.UUIDField(
        _("UUID"), primary_key=True, default=uuid4.uuid4, editable=False
    )
    contact = models.ForeignKey(Contact, models.CASCADE, related_name="message")
    text = models.TextField()
    created_on = models.DateTimeField()
    direction = models.CharField(_("contact name"), max_length=150)
    message_flow_uuid = models.UUIDField(_("flow identification UUID"), unique=True)


class ContactCount(models.Model):
    count = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    day = models.DateTimeField(null=True)
    project = models.ForeignKey("common.Project", models.CASCADE, related_name="contact_count_project", null=True)

    def increase_contact_count(self, contact_count):
        self.count += contact_count
        self.save()
