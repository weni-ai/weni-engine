from ast import arg
import logging
import uuid as uuid4


from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from timezone_field import TimeZoneField

from connect.common.models import Project
from connect.authentication.models import User

from enum import Enum

logger = logging.getLogger(__name__)


class SyncManagerTask(models.Model):
    uuid = models.UUIDField(
        _("UUID"), primary_key=True, default=uuid4.uuid4, editable=False
    )
    status = models.BooleanField(
        default=False, help_text=_("Whether this task succeded or not.")
    )
    task_type = models.CharField(_("task type"), max_length=150)
    started_at = models.DateTimeField(_("started at"))
    finished_at = models.DateTimeField(_("finished at"))
    before = models.DateTimeField(_("before"))
    after = models.DateTimeField(_("after"))


class Channel(models.Model):
    CHANNEL_CHOICES = [
        ("WA", _("WhatsApp")),
        ("TG", _("Telegram")),
    ]
    uuid = models.UUIDField(
        _("UUID"), primary_key=True, default=uuid4.uuid4, editable=False
    )
    name = models.CharField(_("name"), max_length=150)
    channel_type = models.CharField(
        _("channel_type"), max_length=150, choices=CHANNEL_CHOICES
    )
    channel_flow_uuid = models.UUIDField(_("flow identification UUID"), unique=True)
    project = models.ForeignKey(Project, models.CASCADE, related_name="project")

    @staticmethod
    def create(*args, **kwargs):
        if not Channel.is_new_channel(kwargs["channel_flow_uuid"]):
            Channel.objects.create(
                project=kwargs["project"],
                channel_flow_uuid=kwargs["channel_flow_uuid"],
                channel_type=kwargs["channel_type"],
                name=kwargs["name"],
            )

    @staticmethod
    def is_new_channel(channel_flow_uuid):
        return Channel.objects.filter(channel_flow_uuid=channel_flow_uuid).exists()


class ContactManager(models.Manager):
    def create(self, *args, **kwargs):
        contact = self.get_contact(kwargs.get('contact_flow_uuid'))
        if contact.exists():
            return contact.first()
        else:
            return super(ContactManager, self).create(*args, **kwargs)   

    def get_contact(self, contact_flow_uuid):
        return self.filter(
                    created_at__date__month=timezone.now().date().month,
                    created_at__date__year=timezone.now().date().year,
                    contact_flow_uuid=contact_flow_uuid)


class Contact(models.Model):
    uuid = models.UUIDField(
        _("UUID"), primary_key=True, default=uuid4.uuid4, editable=False
    )
    contact_flow_uuid = models.UUIDField(_("flow identification UUID"))
    name = models.CharField(_("contact name"), max_length=150)
    channel = models.ForeignKey(Channel, models.CASCADE, related_name="channel")
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(blank=True, null=True)


    objects = ContactManager()



class Message(models.Model):
    uuid = models.UUIDField(
        _("UUID"), primary_key=True, default=uuid4.uuid4, editable=False
    )
    contact = models.ForeignKey(Contact, models.CASCADE, related_name="message")
    text = models.TextField()
    sent_on = models.DateTimeField()
    direction = models.CharField(_("contact name"), max_length=150)
    message_flow_uuid = models.UUIDField(_("flow identification UUID"), unique=True)


class ContactCount(models.Model):
    channel = models.ForeignKey(
        Channel, models.CASCADE, related_name="contact_count_channel"
    )
    count = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def increase_contact_count(self):
        self.count += len(self.filter())
        # verifica se existe novos
        # contatos e Soma com
        #     o número atual
