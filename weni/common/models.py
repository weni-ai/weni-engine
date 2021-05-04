import uuid as uuid4

from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _
from timezone_field import TimeZoneField

from weni.authentication.models import User
from weni.celery import app as celery_app


class Newsletter(models.Model):
    class Meta:
        verbose_name = _("dashboard newsletter")

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    def __str__(self):
        return f"PK: {self.pk}"


class NewsletterLanguage(models.Model):
    class Meta:
        verbose_name = _("dashboard newsletter language")
        unique_together = ["language", "newsletter"]

    language = models.CharField(
        _("language"),
        max_length=10,
        choices=settings.LANGUAGES,
        default=settings.DEFAULT_LANGUAGE,
    )
    title = models.CharField(_("title"), max_length=50)
    description = models.TextField(_("description"))
    newsletter = models.ForeignKey(
        Newsletter, models.CASCADE, related_name="newsletter"
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    def __str__(self):
        return f"Newsletter PK: {self.newsletter.pk} - {self.language} - {self.title}"


class Organization(models.Model):
    class Meta:
        verbose_name = _("organization")

    uuid = models.UUIDField(
        _("UUID"), primary_key=True, default=uuid4.uuid4, editable=False
    )
    name = models.CharField(_("organization name"), max_length=150)
    description = models.TextField(_("organization description"))
    inteligence_organization = models.IntegerField(_("inteligence organization id"))
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    def __str__(self):
        return f"{self.uuid} - {self.name}"

    def get_user_authorization(self, user):
        if user.is_anonymous:
            return OrganizationAuthorization(organization=self)  # pragma: no cover
        get, created = OrganizationAuthorization.objects.get_or_create(
            user=user, organization=self
        )
        return get


class OrganizationAuthorization(models.Model):
    class Meta:
        verbose_name = _("organization authorization")
        verbose_name_plural = _("organization authorizations")
        unique_together = ["user", "organization"]

    LEVEL_NOTHING = 0
    LEVEL_VIEWER = 1
    LEVEL_CONTRIBUTOR = 2
    LEVEL_ADMIN = 3

    ROLE_NOT_SETTED = 0
    ROLE_VIEWER = 1
    ROLE_CONTRIBUTOR = 2
    ROLE_ADMIN = 3

    ROLE_CHOICES = [
        (ROLE_NOT_SETTED, _("not set")),
        (ROLE_VIEWER, _("viewer")),
        (ROLE_CONTRIBUTOR, _("contributor")),
        (ROLE_ADMIN, _("admin")),
    ]

    uuid = models.UUIDField(
        _("UUID"), primary_key=True, default=uuid4.uuid4, editable=False
    )
    user = models.ForeignKey(User, models.CASCADE, related_name="authorizations_user")
    organization = models.ForeignKey(
        Organization, models.CASCADE, related_name="authorizations"
    )
    role = models.PositiveIntegerField(
        _("role"), choices=ROLE_CHOICES, default=ROLE_NOT_SETTED
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    def __str__(self):
        return f"{self.organization.name} - {self.user.email}"

    @property
    def level(self):
        if self.role == OrganizationAuthorization.ROLE_VIEWER:
            return OrganizationAuthorization.LEVEL_VIEWER

        if self.role == OrganizationAuthorization.ROLE_CONTRIBUTOR:
            return OrganizationAuthorization.LEVEL_CONTRIBUTOR

        if self.role == OrganizationAuthorization.ROLE_ADMIN:
            return OrganizationAuthorization.LEVEL_ADMIN

    @property
    def can_read(self):
        return self.level in [
            OrganizationAuthorization.LEVEL_VIEWER,
            OrganizationAuthorization.LEVEL_CONTRIBUTOR,
            OrganizationAuthorization.LEVEL_ADMIN,
        ]

    @property
    def can_contribute(self):
        return self.level in [
            OrganizationAuthorization.LEVEL_CONTRIBUTOR,
            OrganizationAuthorization.LEVEL_ADMIN,
        ]

    @property
    def can_write(self):
        return self.level in [OrganizationAuthorization.LEVEL_ADMIN]

    @property
    def is_admin(self):
        return self.level == OrganizationAuthorization.LEVEL_ADMIN

    @property
    def role_verbose(self):
        return dict(OrganizationAuthorization.ROLE_CHOICES).get(
            self.role
        )  # pragma: no cover

    def send_new_role_email(self, responsible=None):
        if not settings.SEND_EMAILS:  # pragma: no cover
            return False  # pragma: no cover
        # responsible_name = (
        #     responsible and responsible.name or self.organization.owner.first_name
        # )
        # context = {
        #     "base_url": settings.BASE_URL,
        #     "responsible_name": responsible_name,
        #     "user_name": self.user.first_name,
        #     "repository_name": self.organization.name,
        #     # "repository_url": self.organization.get_absolute_url(),
        #     "new_role": self.role_verbose,
        # }
        # send_mail(
        #     _("New role in {}").format(self.organization.name),
        #     render_to_string("common/emails/new_role.txt", context),
        #     None,
        #     [self.user.user.email],
        #     html_message=render_to_string("common/emails/new_role.html", context),
        # )


class Project(models.Model):
    class Meta:
        verbose_name = _("project")
        unique_together = ["flow_organization"]

    DATE_FORMAT_DAY_FIRST = "D"
    DATE_FORMAT_MONTH_FIRST = "M"
    DATE_FORMATS = (
        (DATE_FORMAT_DAY_FIRST, "DD-MM-YYYY"),
        (DATE_FORMAT_MONTH_FIRST, "MM-DD-YYYY"),
    )

    uuid = models.UUIDField(
        _("UUID"), primary_key=True, default=uuid4.uuid4, editable=False
    )
    name = models.CharField(_("project name"), max_length=150)
    organization = models.ForeignKey(
        Organization, models.CASCADE, related_name="project"
    )
    timezone = TimeZoneField(verbose_name=_("Timezone"))
    date_format = models.CharField(
        verbose_name=_("Date Format"),
        max_length=1,
        choices=DATE_FORMATS,
        default=DATE_FORMAT_DAY_FIRST,
        help_text=_("Whether day comes first or month comes first in dates"),
    )
    flow_organization = models.UUIDField(_("flow identification UUID"), unique=True)
    inteligence_count = models.IntegerField(_("Intelligence count"), default=0)
    flow_count = models.IntegerField(_("Flows count"), default=0)
    contact_count = models.IntegerField(_("Contacts count"), default=0)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    def __str__(self):
        return f"{self.uuid} - Project: {self.name} - Org: {self.organization.name}"


class Service(models.Model):
    class Meta:
        verbose_name = _("service")

    SERVICE_TYPE_FLOWS = "type_service_flows"
    SERVICE_TYPE_INTELIGENCE = "type_service_inteligence"
    SERVICE_TYPE_CHAT = "type_service_chat"

    SERVICE_TYPE_CHOICES = [
        (
            SERVICE_TYPE_FLOWS,
            _("Flows service"),
        ),
        (
            SERVICE_TYPE_INTELIGENCE,
            _("Inteligence Service"),
        ),
        (
            SERVICE_TYPE_CHAT,
            _("Chat Service"),
        ),
    ]

    REGION_IRELAND = "region_ireland"
    REGION_VIRGINIA = "region_virginia"
    REGION_SAO_PAULO = "region_sao_paulo"

    REGION_CHOICES = [
        (
            REGION_IRELAND,
            _("Region Ireland"),
        ),
        (
            REGION_VIRGINIA,
            _("Region Virginia"),
        ),
        (
            REGION_SAO_PAULO,
            _("Region São Paulo"),
        ),
    ]

    url = models.URLField(_("service url"), unique=True)
    service_type = models.CharField(
        _("service type"),
        max_length=50,
        choices=SERVICE_TYPE_CHOICES,
        default=SERVICE_TYPE_CHAT,
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    default = models.BooleanField(_("standard service for all projects"), default=False)
    region = models.CharField(
        _("service region"),
        max_length=50,
        choices=REGION_CHOICES,
        default=REGION_SAO_PAULO,
    )
    maintenance = models.BooleanField(
        _("Define if the service is under maintenance"), default=False
    )

    def __str__(self):
        return self.url


class LogService(models.Model):
    class Meta:
        verbose_name = _("log service")

    service = models.ForeignKey(Service, models.CASCADE, related_name="log_service")
    status = models.BooleanField(_("status service"), default=False)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)


class ServiceStatus(models.Model):
    class Meta:
        verbose_name = _("service status")
        ordering = ["created_at"]
        unique_together = ["service", "project"]

    service = models.ForeignKey(Service, models.CASCADE)
    project = models.ForeignKey(Project, models.CASCADE, related_name="service_status")
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    def __str__(self):
        return self.service.url  # pragma: no cover


@receiver(post_save, sender=Project)
def create_service_status(sender, instance, created, **kwargs):
    if created:
        for service in Service.objects.filter(default=True):
            instance.service_status.create(service=service)


@receiver(post_save, sender=Service)
def create_service_default_in_all_user(sender, instance, created, **kwargs):
    if created and instance.default:
        for project in Project.objects.all():
            project.service_status.create(service=instance)


@receiver(post_save, sender=Organization)
def update_organization(sender, instance, **kwargs):
    celery_app.send_task(
        "update_organization",
        args=[instance.inteligence_organization, instance.name],
    )


@receiver(post_save, sender=OrganizationAuthorization)
def org_authorizations(sender, instance, **kwargs):
    celery_app.send_task(
        "update_user_permission_organization",
        args=[
            instance.organization.inteligence_organization,
            instance.user.email,
            instance.role,
        ],
    )
    for project in instance.organization.project.all():
        celery_app.send_task(
            "update_user_permission_project",
            args=[
                project.flow_organization,
                instance.user.email,
                instance.role,
            ],
        )
