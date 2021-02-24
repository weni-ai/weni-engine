import uuid as uuid4
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _
from timezone_field import TimeZoneField

from weni.authentication.models import User


class Newsletter(models.Model):
    class Meta:
        verbose_name = _("dashboard newsletter")

    title = models.CharField(_("title"), max_length=36)
    description = models.TextField(_("description"))
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    def __str__(self):
        return self.title


class Organization(models.Model):
    class Meta:
        verbose_name = _("organization")

    uuid = models.UUIDField(
        verbose_name=_("Organization UUID"),
        primary_key=True,
        default=uuid4.uuid4,
        editable=False,
    )
    name = models.CharField(verbose_name=_("Organization Name"), max_length=128)
    description = models.TextField(verbose_name=_("Organization Description"))
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, help_text=_("Organization Owner")
    )


class OrgProject(models.Model):
    class Meta:
        verbose_name = _("organization project")

    DATE_FORMAT_DAY_FIRST = "D"
    DATE_FORMAT_MONTH_FIRST = "M"
    DATE_FORMATS = (
        (DATE_FORMAT_DAY_FIRST, "DD-MM-YYYY"),
        (DATE_FORMAT_MONTH_FIRST, "MM-DD-YYYY"),
    )

    uuid = models.UUIDField(
        verbose_name=_("Organization UUID"),
        primary_key=True,
        default=uuid4.uuid4,
        editable=False,
    )
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    name = models.CharField(verbose_name=_("Project Name"), max_length=128)
    timezone = TimeZoneField(verbose_name=_("Timezone"))
    # country = models.ForeignKey(
    #     "locations.AdminBoundary",
    #     null=True,
    #     blank=True,
    #     on_delete=models.PROTECT,
    #     help_text="The country this organization should map results for.",
    # )
    date_format = models.CharField(
        verbose_name=_("Date Format"),
        max_length=1,
        choices=DATE_FORMATS,
        default=DATE_FORMAT_DAY_FIRST,
        help_text=_("Whether day comes first or month comes first in dates"),
    )
    # config = JSONAsTextField(
    #     null=True,
    #     default=dict,
    #     verbose_name=_("Configuration"),
    #     help_text=_("More Organization specific configuration"),
    # )
    slug = models.SlugField(
        verbose_name=_("Slug"),
        max_length=255,
        null=True,
        blank=True,
        unique=True,
        error_messages=dict(unique=_("This slug is not available")),
    )
    is_anon = models.BooleanField(
        default=False,
        help_text=_(
            "Whether this organization anonymizes the phone numbers of contacts within it"
        ),
    )
    is_flagged = models.BooleanField(
        default=False, help_text=_("Whether this organization is currently flagged.")
    )
    is_suspended = models.BooleanField(
        default=False, help_text=_("Whether this organization is currently suspended.")
    )
    primary_language = models.IntegerField(
        null=True,
        blank=True,
        help_text=_(
            "The primary language will be used for contacts with no language preference."
        ),
    )
    brand = models.CharField(
        max_length=128,
        verbose_name=_("Brand"),
        help_text=_("The brand used in emails"),
    )
    flow_org_id = models.UUIDField(
        verbose_name=_("UUID of the organization without service flow"),
        default=uuid4.uuid4,
    )


class Service(models.Model):
    class Meta:
        verbose_name = _("service")

    TYPE_SERVICE_FLOWS = "type_service_flows"
    TYPE_SERVICE_INTELIGENCE = "type_service_inteligence"
    TYPE_SERVICE_CHAT = "type_service_chat"

    TYPE_SERVICE_CHOICES = [
        (
            TYPE_SERVICE_FLOWS,
            _("Flows service"),
        ),
        (
            TYPE_SERVICE_INTELIGENCE,
            _("Inteligence Service"),
        ),
        (
            TYPE_SERVICE_CHAT,
            _("Chat Service"),
        ),
    ]

    url = models.URLField(_("service url"), unique=True)
    status = models.BooleanField(_("status service"), default=False)
    type_service = models.CharField(
        _("type service"),
        max_length=50,
        choices=TYPE_SERVICE_CHOICES,
        default=TYPE_SERVICE_CHAT,
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    last_updated = models.DateTimeField(_("last updated"), auto_now_add=True)
    default = models.BooleanField(_("service default"), default=False)

    def __str__(self):
        return self.url


class ServiceStatus(models.Model):
    class Meta:
        verbose_name = _("service status")
        ordering = ["created_at"]
        unique_together = ["service", "org_project"]

    service = models.ForeignKey(Service, models.CASCADE)
    org_project = models.ForeignKey(OrgProject, models.CASCADE, related_name="service_status")
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    def __str__(self):
        return self.service.url


@receiver(post_save, sender=User)
def create_service_status(sender, instance, created, **kwargs):
    if created:
        for service in Service.objects.filter(default=True):
            instance.service_status.create(service=service)


@receiver(post_save, sender=Service)
def create_service_default_in_all_user(sender, instance, created, **kwargs):
    if created and instance.default:
        for user in User.objects.all():
            user.service_status.create(service=instance)
