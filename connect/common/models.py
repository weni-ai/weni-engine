import decimal
import logging
import uuid as uuid4
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core import mail
from django.db import models
from django.db.models import Sum
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from timezone_field import TimeZoneField

from connect import billing
from connect.authentication.models import User
from connect.billing.gateways.stripe_gateway import StripeGateway

from enum import Enum

logger = logging.getLogger(__name__)


class Newsletter(models.Model):
    class Meta:
        verbose_name = _("newsletter")
        verbose_name_plural = _("newsletters")

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    def __str__(self):
        return f"PK: {self.pk}"


class NewsletterLanguage(models.Model):
    class Meta:
        verbose_name = _("dashboard newsletter language")
        verbose_name_plural = _("newsletter languages")
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


class OrganizationManager(models.Manager):
    def create(
        self,
        organization_billing__cycle,
        organization_billing__plan,
        organization_billing__payment_method=None,
        *args,
        **kwargs,
    ):
        instance = super().create(*args, **kwargs)
        new_kwargs = {}

        if organization_billing__cycle:
            new_kwargs.update(
                {
                    "cycle": organization_billing__cycle,
                }
            )

            if (
                BillingPlan.BILLING_CYCLE_DAYS.get(organization_billing__cycle)
                is not None
            ):
                new_kwargs.update(
                    {
                        "next_due_date": timezone.localtime(
                            timezone.now()
                            + timedelta(
                                BillingPlan.BILLING_CYCLE_DAYS.get(
                                    organization_billing__cycle
                                )
                            )
                        ).date()
                    }
                )
        if organization_billing__payment_method:
            new_kwargs.update({"payment_method": organization_billing__payment_method})
        if organization_billing__plan:
            new_kwargs.update({"plan": organization_billing__plan})

        BillingPlan.objects.create(organization=instance, **new_kwargs)
        return instance


class Organization(models.Model):
    class Meta:
        verbose_name = _("organization")
        verbose_name_plural = _("organizations")

    uuid = models.UUIDField(
        _("UUID"), primary_key=True, default=uuid4.uuid4, editable=False
    )
    name = models.CharField(_("organization name"), max_length=150)
    description = models.TextField(_("organization description"))
    inteligence_organization = models.IntegerField(_("inteligence organization id"))
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    is_suspended = models.BooleanField(
        default=False, help_text=_("Whether this organization is currently suspended.")
    )
    extra_integration = models.IntegerField(_("Whatsapp Extra Integration"), default=0)
    objects = OrganizationManager()

    def __str__(self):
        return f"{self.uuid} - {self.name}"

    def get_user_authorization(self, user, **kwargs):
        if user.is_anonymous:
            return OrganizationAuthorization(organization=self)  # pragma: no cover
        get, created = OrganizationAuthorization.objects.get_or_create(
            user=user,
            organization=self,
            **kwargs,
        )
        return get

    def send_email_invite_organization(self, email):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "webapp_base_url": settings.WEBAPP_BASE_URL,
            "organization_name": self.name,
        }
        mail.send_mail(
            _("Invitation to join organization"),
            render_to_string("common/emails/organization/invite_organization.txt", context),
            None,
            [email],
            html_message=render_to_string(
                "common/emails/organization/invite_organization.html", context
            ),
        )
        return mail

    def send_email_organization_going_out(self, user_name: str, email: str):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "user_name": user_name,
            "organization_name": self.name
        }
        mail.send_mail(
            _(f"You are going out of {self.name}"),
            render_to_string("common/emails/organization/org_going_out.txt", context),
            None,
            [email],
            html_message=render_to_string("common/emails/organization/org_going_out.html", context)
        )
        return mail

    def send_email_organization_removed(self, email: str, user_name: str):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "user_name": user_name,
            "organization_name": self.name
        }
        mail.send_mail(
            _(f"You have been removed from {self.name}"),
            render_to_string("common/emails/organization/org_removed.txt", context),
            None,
            [email],
            html_message=render_to_string("common/emails/organization/org_removed.html", context)
        )
        return mail

    def send_email_organization_create(self, email: str, first_name: str):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "webapp_base_url": settings.WEBAPP_BASE_URL,
            "organization_name": self.name,
            "first_name": first_name,
        }
        mail.send_mail(
            _("Organization created!"),
            render_to_string("common/emails/organization/organization_create.txt", context),
            None,
            [email],
            html_message=render_to_string(
                "common/emails/organization/organization_create.html", context
            ),
        )
        return mail

    def send_email_remove_permission_organization(self, first_name: str, email: str):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "organization_name": self.name,
            "first_name": first_name,
        }
        mail.send_mail(
            _(f"You have been removed from the {self.name}"),
            render_to_string(
                "common/emails/organization/remove_permission_organization.txt", context
            ),
            None,
            [email],
            html_message=render_to_string(
                "common/emails/organization/remove_permission_organization.html", context
            ),
        )
        return mail

    def send_email_delete_organization(self, first_name: str, email: str):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "organization_name": self.name,
            "first_name": first_name,
        }
        mail.send_mail(
            _(f"{self.name} no longer exists!"),
            render_to_string("common/emails/organization/delete_organization.txt", context),
            None,
            [email],
            html_message=render_to_string(
                "common/emails/organization/delete_organization.html", context
            ),
        )
        return mail

    def send_email_change_organization_name(self, user_name: str, email: str, organization_previous_name: str,
                                            organization_new_name: str):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "user_name": user_name,
            "organization_previous_name": organization_previous_name,
            "organization_new_name": organization_new_name
        }
        mail.send_mail(
            _(f"{organization_previous_name} now it's {organization_new_name}"),
            render_to_string("common/emails/organization/change_organization_name.txt", context),
            None,
            [email],
            html_message=render_to_string(
                "common/emails/organization/change_organization_name.html", context
            ),
        )
        return mail

    def send_email_access_code(self, email: str, user_name: str, access_code: str):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "access_code": access_code,
            "user_name": user_name,
        }
        mail.send_mail(
            _("You receive an access code to Weni Platform"),
            render_to_string("authentication/emails/access_code.txt", context),
            None,
            [email],
            html_message=render_to_string(
                "authentication/emails/access_code.html", context
            ),
        )
        return mail

    def send_email_permission_change(self, user_name: str, old_permission: str, new_permission: str, email: str):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "user_name": user_name,
            "old_permission": old_permission,
            "new_permission": new_permission
        }
        mail.send_mail(
            _("A new permission has been assigned to you"),
            render_to_string("common/emails/organization/permission_change.txt", context),
            None,
            [email],
            html_message=render_to_string(
                "common/emails/organization/permission_change.html", context
            ),
        )
        return mail

    @property
    def active_contacts(self):
        active_contact_counter = 0
        for project in self.project.all():
            active_contact_counter += project.contact_count
        return active_contact_counter

    @property
    def extra_active_integrations(self):
        active_integrations_counter = 0
        for project in self.project.all():
            active_integrations_counter += project.extra_active_integration
        return 0 if active_integrations_counter <= 1 else active_integrations_counter - 1


class OrganizationLevelRole(Enum):
    NOTHING, CONTRIBUTOR, ADMIN, FINANCIAL = list(range(4))


class OrganizationRole(Enum):
    NOT_SETTED, CONTRIBUTOR, ADMIN, FINANCIAL = list(range(4))


class OrganizationAuthorization(models.Model):
    class Meta:
        verbose_name = _("organization authorization")
        verbose_name_plural = _("organization authorizations")
        unique_together = ["user", "organization"]

    ROLE_CHOICES = [
        (OrganizationRole.NOT_SETTED.value, _("not set")),
        (OrganizationRole.CONTRIBUTOR.value, _("contributor")),
        (OrganizationRole.ADMIN.value, _("admin")),
        (OrganizationRole.FINANCIAL.value, _('financial')),
    ]

    uuid = models.UUIDField(
        _("UUID"), primary_key=True, default=uuid4.uuid4, editable=False
    )
    user = models.ForeignKey(User, models.CASCADE, related_name="authorizations_user")
    organization = models.ForeignKey(
        Organization, models.CASCADE, related_name="authorizations"
    )
    role = models.PositiveIntegerField(
        _("role"), choices=ROLE_CHOICES, default=OrganizationRole.NOT_SETTED.value
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    def __str__(self):
        return f"{self.organization.name} - {self.user.email}"

    @property
    def level(self):
        if self.role == OrganizationRole.CONTRIBUTOR.value:
            return OrganizationLevelRole.CONTRIBUTOR.value

        if self.role == OrganizationRole.ADMIN.value:
            return OrganizationLevelRole.ADMIN.value

        if self.role == OrganizationRole.FINANCIAL.value:
            return OrganizationLevelRole.FINANCIAL.value

    @property
    def can_read(self):
        return self.level in [
            OrganizationLevelRole.FINANCIAL.value,
            OrganizationLevelRole.CONTRIBUTOR.value,
            OrganizationLevelRole.ADMIN.value,
        ]

    @property
    def can_contribute(self):
        return self.level in [
            OrganizationLevelRole.CONTRIBUTOR.value,
            OrganizationLevelRole.ADMIN.value,
        ]

    @property
    def can_write(self):
        return self.level in [OrganizationLevelRole.ADMIN.value]

    @property
    def is_admin(self):
        return self.level == OrganizationLevelRole.ADMIN.value

    @property
    def is_financial(self):
        return self.level == OrganizationLevelRole.FINANCIAL.value

    @property
    def can_contribute_billing(self):
        return self.level in [OrganizationLevelRole.ADMIN.value, OrganizationLevelRole.FINANCIAL.value]

    @property
    def role_verbose(self):
        return dict(OrganizationAuthorization.ROLE_CHOICES).get(
            self.role
        )  # pragma: no cover

    def send_new_role_email(self, responsible=None):
        if not settings.SEND_EMAILS:  # pragma: no cover
            return False  # pragma: no cover


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
    extra_active_integration = models.IntegerField(_("Whatsapp Integrations"), default=0)

    def __str__(self):
        return f"{self.uuid} - Project: {self.name} - Org: {self.organization.name}"

    def get_user_authorization(self, user, **kwargs):
        if user.is_anonymous:
            return ProjectAuthorization(project=self)  # pragma: no cover
        get, created = ProjectAuthorization.objects.get_or_create(
            user=user,
            project=self,
            organization_authorization=self.organization.authorizations.first(),
            **kwargs,
        )
        return get

    def send_email_create_project(self, first_name: str, email: str):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "organization_name": self.organization.name,
            "project_name": self.name,
            "first_name": first_name,
        }
        mail.send_mail(
            _(f"You have been invited to join the {self.name} organization"),
            render_to_string("common/emails/project/project_create.txt", context),
            None,
            [email],
            html_message=render_to_string(
                "common/emails/project/project_create.html", context
            ),
        )
        return mail

    def send_email_change_project(self, first_name: str, email: str, info: dict):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover

        old_project_name = info.get("old_project_name")
        date_before = info.get("date_before")
        timezone_before = info.get("old_timezone")
        country_loc_suport_before = info.get("country_loc_suport_before")
        country_loc_suport_now = info.get("country_loc_suport_now")
        default_lang_before = info.get("default_lang_before")
        default_lang_now = info.get("default_lang_now")
        secondary_lang_before = info.get("secondary_lang_before")
        secondary_lang_now = info.get("secondary_lang_now")
        user = info.get("user")

        context = {
            "base_url": settings.BASE_URL,
            "organization_name": self.organization.name,
            "project_name": self.name,
            "old_project_name": old_project_name,
            "first_name": first_name,
            "user": user,
            "date_before": date_before,
            "date_now": self.date_format,
            "timezone_before": timezone_before,
            "timezone_now": str(self.timezone),
            "country_loc_suport_before": country_loc_suport_before,
            "country_loc_suport_now": country_loc_suport_now,
            "default_lang_before": default_lang_before,
            "default_lang_now": default_lang_now,
            "secondary_lang_before": secondary_lang_before,
            "secondary_lang_now": secondary_lang_now,
        }
        mail.send_mail(
            _(f"The project {self.name} has changed"),
            render_to_string("common/emails/project/project-changed.txt", context),
            None,
            [email],
            html_message=render_to_string(
                "common/emails/project/project-changed.html", context
            ),
        )
        return mail

    def send_email_deleted_project(self, first_name: str, email: str):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "organization_name": self.organization.name,
            "project_name": self.name,
            "first_name": first_name,
        }
        mail.send_mail(
            _("A project was deleted..."),
            render_to_string("common/emails/project/project-delete.txt", context),
            None,
            [email],
            html_message=render_to_string(
                "common/emails/project/project-delete.html", context
            ),
        )
        return mail


class ProjectRole(Enum):
    NOT_SETTED, ADMIN, CONTRIBUTOR, VIEWER = list(range(4))


class ProjectRoleLevel(Enum):
    NOTHING, ADMIN, CONTRIBUTOR, VIEWER = list(range(4))


class ProjectAuthorization(models.Model):
    ROLE_CHOICES = [
        (ProjectRole.NOT_SETTED.value, _("not set")),
        (ProjectRole.VIEWER.value, _("viewer")),
        (ProjectRole.CONTRIBUTOR.value, _("contributor")),
        (ProjectRole.ADMIN.value, _("admin")),
    ]
    uuid = models.UUIDField(
        _("UUID"), primary_key=True, default=uuid4.uuid4, editable=False
    )
    user = models.ForeignKey(User, models.CASCADE, related_name="project_authorizations_user")
    project = models.ForeignKey(Project, models.CASCADE, related_name="project_authorizations")
    organization_authorization = models.ForeignKey(OrganizationAuthorization, models.CASCADE)
    role = models.PositiveIntegerField(
        _("role"), choices=ROLE_CHOICES, default=ProjectRole.NOT_SETTED.value
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    def __str__(self):
        return f'{self.project.name} - {self.user.email}'

    @property
    def level(self):
        if self.role == ProjectRole.ADMIN.value:
            return ProjectRoleLevel.ADMIN.value
        elif self.role == ProjectRole.CONTRIBUTOR.value:
            return ProjectRoleLevel.CONTRIBUTOR.value
        elif self.role == ProjectRole.VIEWER.value:
            return ProjectRoleLevel.VIEWER.value

    @property
    def is_admin(self):
        return self.level == ProjectRoleLevel.ADMIN.value

    @property
    def can_write(self):
        return self.level in [ProjectRoleLevel.ADMIN.value]

    @property
    def can_read(self):
        return self.level in [ProjectRoleLevel.ADMIN.value, ProjectRoleLevel.CONTRIBUTOR.value, ProjectRoleLevel.VIEWER.value]

    @property
    def can_contribute(self):
        return self.level in [ProjectRoleLevel.ADMIN.value, ProjectRoleLevel.CONTRIBUTOR.value]


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
    start_maintenance = models.DateTimeField(
        _("date start maintenance"), auto_now_add=True
    )

    def __str__(self):
        return self.url


class LogService(models.Model):
    class Meta:
        verbose_name = _("log service")
        verbose_name_plural = _("log services")

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


class RequestPermissionOrganization(models.Model):
    class Meta:
        verbose_name = _("request permission organization")
        unique_together = ["email", "organization"]

    email = models.EmailField(_("email"))
    organization = models.ForeignKey(Organization, models.CASCADE)
    role = models.PositiveIntegerField(
        _("role"),
        choices=OrganizationAuthorization.ROLE_CHOICES,
        default=OrganizationRole.NOT_SETTED.value,
    )
    created_by = models.ForeignKey(User, models.CASCADE)


class BillingPlan(models.Model):
    class Meta:
        verbose_name = _("organization billing plan")
        unique_together = ["organization"]

    BILLING_CYCLE_FREE = "billing_free"
    BILLING_CYCLE_SINGLE = "billing_single"
    BILLING_CYCLE_MONTHLY = "billing_monthly"
    BILLING_CYCLE_QUARTERLY = "billing_quarterly"
    BILLING_CYCLE_SEMESTER = "billing_semester"
    BILLING_CYCLE_ANNUAL = "billing_annual"
    BILLING_CYCLE_BIENAL = "billing_bienal"
    BILLING_CYCLE_TRIENAL = "billing_trienal"

    BILLING_CHOICES = [
        (BILLING_CYCLE_FREE, _("free")),
        (BILLING_CYCLE_SINGLE, _("single")),
        (BILLING_CYCLE_MONTHLY, _("monthly")),
        (BILLING_CYCLE_QUARTERLY, _("quarterly")),
        (BILLING_CYCLE_SEMESTER, _("semester")),
        (BILLING_CYCLE_ANNUAL, _("annual")),
        (BILLING_CYCLE_BIENAL, _("bienal")),
        (BILLING_CYCLE_TRIENAL, _("trienal")),
    ]

    BILLING_CYCLE_DAYS = {
        BILLING_CYCLE_FREE: None,
        BILLING_CYCLE_SINGLE: None,
        BILLING_CYCLE_MONTHLY: 30,
        BILLING_CYCLE_QUARTERLY: 90,
        BILLING_CYCLE_SEMESTER: 180,
        BILLING_CYCLE_ANNUAL: 365,
        BILLING_CYCLE_BIENAL: 730,
        BILLING_CYCLE_TRIENAL: 1095,
    }

    PAYMENT_METHOD_CREDIT_CARD = "credit_card"
    PAYMENT_METHOD_PAYMENT_SLIP = "payment_slip"

    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_METHOD_CREDIT_CARD, _("credit card")),
        (PAYMENT_METHOD_PAYMENT_SLIP, _("payment slip")),
    ]

    PLAN_FREE = "free"
    PLAN_ENTERPRISE = "enterprise"
    PLAN_CUSTOM = "custom"

    PLAN_CHOICES = [
        (PLAN_FREE, _("free")),
        (PLAN_ENTERPRISE, _("enterprise")),
        (PLAN_CUSTOM, _("custom"))
    ]

    organization = models.OneToOneField(
        Organization, models.CASCADE, related_name="organization_billing"
    )
    cycle = models.CharField(
        _("billing cycle"),
        max_length=20,
        choices=BILLING_CHOICES,
        default=BILLING_CYCLE_MONTHLY,
    )
    payment_method = models.CharField(
        _("payment method"), max_length=12, choices=PAYMENT_METHOD_CHOICES, null=True
    )
    last_invoice_date = models.DateField(_("last invoice"), null=True)
    next_due_date = models.DateField(_("next due date"), null=True)
    termination_date = models.DateField(_("termination date"), null=True)
    notes_administration = models.TextField(
        _("notes administration"), null=True, blank=True
    )
    fixed_discount = models.FloatField(_("fixed discount"), default=0)
    plan = models.CharField(_("plan"), max_length=10, choices=PLAN_CHOICES, default=PLAN_CUSTOM)
    contract_on = models.DateField(_("date of contract plan"), auto_now_add=True)
    is_active = models.BooleanField(_("active plan"), default=True)
    stripe_customer = models.CharField(
        verbose_name=_("Stripe Customer"),
        max_length=32,
        null=True,
        blank=True,
        help_text=_("Our Stripe customer id for your organization"),
    )
    stripe_configured_card = models.BooleanField(
        verbose_name=_("Stripe Customer Configured Card"), default=False
    )
    final_card_number = models.IntegerField(
        verbose_name=_("Final Card Number"), null=True, blank=True
    )
    card_expiration_date = models.CharField(
        verbose_name=_("Card Expiration Date"), null=True, blank=True, max_length=6
    )
    cardholder_name = models.TextField(
        verbose_name=_("Cardholder Name"), null=True, blank=True
    )
    card_brand = models.CharField(
        verbose_name=_("Card Brand"), null=True, blank=True, max_length=24
    )

    personal_identification_number = models.CharField(
        verbose_name="Personal Identification Number", null=True, blank=True,
        max_length=50
    )

    additional_billing_information = models.CharField(
        verbose_name=_("Additional billing information"),
        null=True, blank=True, max_length=250
    )

    @property
    def get_stripe_customer(self):
        import stripe

        stripe.api_key = settings.BILLING_SETTINGS.get("stripe", {}).get("API_KEY")
        if not self.stripe_customer:
            customer = stripe.Customer.create(
                name=self.organization.name,
                description=f"ORG: {self.organization.pk}",
            )
            self.stripe_customer = customer.id
            self.save(update_fields=["stripe_customer"])
            return customer

        try:
            customer = stripe.Customer.retrieve(self.stripe_customer)
            return customer
        except stripe.error.InvalidRequestError:
            self.stripe_customer = None
            self.save(update_fields=["stripe_customer"])
            self.get_stripe_customer
        except Exception as e:
            logger.error(f"Could not get Stripe customer: {str(e)}", exc_info=True)
            return None

    @property
    def invoice_warning(self):
        invoice = self.organization.organization_billing_invoice.filter(
            models.Q(payment_status=Invoice.PAYMENT_STATUS_PENDING)
            & models.Q(capture_payment=False)
        )
        return invoice.distinct()

    def allow_payments(self):
        self.organization.organization_billing_invoice.filter(
            models.Q(payment_status=Invoice.PAYMENT_STATUS_PENDING)
            & models.Q(capture_payment=False)
        ).update(capture_payment=True)

    @property
    def problem_capture_invoice(self):
        return True if 0 < len(self.invoice_warning) else False

    @property
    def payment_warnings(self):
        w = []
        if 0 < len(self.invoice_warning):
            w.append(_("Unable to make payment"))
        return w

    @property
    def remove_credit_card(self):
        gateway = billing.get_gateway("stripe")
        unstore = gateway.unstore(identification=self.stripe_customer)
        if unstore['status'] == 'SUCCESS':
            self.card_brand = None
            self.card_expiration_date = None
            self.final_card_number = None
            self.cardholder_name = None
            self.stripe_configured_card = False
            self.save()
            return True
        return False

    @staticmethod
    def calculate_amount(contact_count: int):
        precification = GenericBillingData.get_generic_billing_data_instance()
        return Decimal(
            str(precification.calculate_active_contacts(contact_count=contact_count))
        ).quantize(Decimal(".01"), decimal.ROUND_HALF_UP)

    @property
    def currenty_invoice(self):
        contact_count = self.organization.project.aggregate(
            total_contact_count=Sum("contact_count")
        ).get("total_contact_count")

        amount_currenty = 0

        if self.plan == BillingPlan.PLAN_ENTERPRISE:
            amount_currenty = Decimal(
                float(
                    float(
                        self.organization.organization_billing.calculate_amount(
                            contact_count=0 if contact_count is None else contact_count
                        )
                    ) + (settings.BILLING_COST_PER_WHATSAPP * self.organization.extra_integration)
                )
                * float(1 - self.fixed_discount / 100)
            ).quantize(Decimal(".01"), decimal.ROUND_HALF_UP)

        return {
            "total_contact": contact_count,
            "amount_currenty": amount_currenty
        }

    def change_plan(self, plan):
        _is_valid = False
        for choice in self.PLAN_CHOICES:
            if plan in choice:
                _is_valid = True
                self.plan = choice[0]
                self.save()
                # send mail here
                break
        return _is_valid

    def add_additional_information(self, data: dict):
        count = 0
        if not (data['additional_info'] is None):
            self.additional_billing_information = data['additional_info']
            count += 1
        if not (data['personal_identification_number'] is None):
            self.personal_identification_number = data['personal_identification_number']
            count += 1
        if not (data['extra_integration'] is None):
            self.organization.extra_integration = data['extra_integration']
            self.organization.save()
            count += 1
        if count > 0:
            self.save()
            return 0
        elif count == 0:
            return 1

    def send_email_added_card(self, user_name: str, email: list):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "organization_name": self.organization.name,
            "user_name": user_name
        }
        mail.send_mail(
            _(f"A credit card has been added to the organization {self.organization.name}"),
            render_to_string("billing/emails/added_card.txt", context),
            None,
            email,
            html_message=render_to_string("billing/emails/added_card.html", context)
        )
        return mail

    def send_email_changed_card(self, user_name: str, email: str):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "organization_name": self.organization.name,
            "user_name": user_name
        }
        mail.send_mail(
            _(f"A credit card has been changed to the organization {self.organization.name}"),
            render_to_string("billing/emails/changed_card.txt", context),
            None,
            email,
            html_message=render_to_string("billing/emails/changed_card.html", context)
        )
        return mail

    def send_email_finished_plan(self, user_name: str, email: list):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "organization_name": self.organization.name,
            "user_name": user_name
        }
        mail.send_mail(
            _(f"Your {self.organization.name} organization's plan has ended"),
            render_to_string("billing/emails/finished-plan.txt", context),
            None,
            email,
            html_message=render_to_string("billing/emails/finished-plan.html", context)
        )
        return mail

    def send_email_reactivated_plan(self, user_name: str, email: list):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "organization_name": self.organization.name,
            "user_name": user_name
        }
        mail.send_mail(
            _(f"Your {self.organization.name} organization's plan has been reactivated."),
            render_to_string("billing/emails/reactived-plan.txt", context),
            None,
            email,
            html_message=render_to_string("billing/emails/reactived-plan.html", context)
        )
        return mail

    def send_email_removed_credit_card(self, user_name: str, email: list):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "user_name": user_name,
            "org_name": self.organization.name
        }
        mail.send_mail(
            _(f"Your {self.organization.name} organization credit card was removed"),
            render_to_string("billing/emails/removed_card.txt", context),
            None,
            email,
            html_message=render_to_string("billing/emails/removed_card.html", context)
        )
        return mail

    def send_email_expired_free_plan(self, user_name: str, email: list):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "organization_name": self.organization.name,
            "user_name": user_name
        }
        mail.send_mail(
            _(f"The organization {self.organization.name} has already surpassed 200 active contacts"),
            render_to_string("billing/emails/free-plan-expired.txt", context),
            None,
            email,
            html_message=render_to_string("billing/emails/free-plan-expired.html", context)
        )
        return mail

    def send_email_chosen_plan(self, user_name: str, email: str, plan: str):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "user_name": user_name,
            "org_name": self.organization.name,
            "plan": plan
        }
        mail.send_mail(
            _(f"Your {self.organization.name} organization has the {plan.title()} Plan"),
            render_to_string("billing/emails/free_plan.txt", context),
            None,
            [email],
            html_message=render_to_string("billing/emails/free_plan.html", context)
        )
        return mail

    def send_email_changed_plan(self, user_name: str, email: list, old_plan: str):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "organization_name": self.organization.name,
            "user_name": user_name,
            "old_plan": old_plan,
            "actual_plan": self.plan
        }
        mail.send_mail(
            _(f"Your {self.organization.name} organization's plan has been changed."),
            render_to_string("billing/emails/changed-plan.txt", context),
            None,
            email,
            html_message=render_to_string("billing/emails/changed-plan.html", context)
        )
        return mail


class Invoice(models.Model):
    class Meta:
        verbose_name = _("organization billing invoice")

    PAYMENT_STATUS_PENDING = "pending"
    PAYMENT_STATUS_PAID = "paid"
    PAYMENT_STATUS_CANCELED = "canceled"
    PAYMENT_STATUS_FRAUD = "fraud"

    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_STATUS_PENDING, _("pending")),
        (PAYMENT_STATUS_PAID, _("paid")),
        (PAYMENT_STATUS_CANCELED, _("canceled")),
        (PAYMENT_STATUS_FRAUD, _("fraud")),
    ]

    organization = models.ForeignKey(
        Organization, models.CASCADE, related_name="organization_billing_invoice"
    )
    invoice_random_id = models.IntegerField(_("incremental invoice amount"), default=1)
    due_date = models.DateField(_("due date"), null=True)
    paid_date = models.DateField(_("paid date"), null=True)
    payment_status = models.CharField(
        _("payment status"),
        max_length=8,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_STATUS_PENDING,
    )
    payment_method = models.CharField(
        _("payment method"),
        max_length=12,
        choices=BillingPlan.PAYMENT_METHOD_CHOICES,
        null=True,
    )
    discount = models.FloatField(_("discount"), default=0)
    notes = models.TextField(_("notes"), null=True, blank=True)
    stripe_charge = models.CharField(
        verbose_name=_("Stripe Charge Id"),
        max_length=32,
        null=True,
        blank=True,
        help_text=_("The Stripe charge id for this charge"),
    )
    capture_payment = models.BooleanField(
        default=True,
        help_text=_(
            "Controls whether the system will capture the payment, "
            "if not successful, the user will receive an alert to adjust the payment data"
        ),
    )
    extra_integration = models.IntegerField(_("Whatsapp Extra Integration"), default=0)
    cost_per_whatsapp = models.DecimalField(
        _("cost per whatsapp"), decimal_places=2, max_digits=11, default=0
    )

    @property
    def card_data(self):
        card_data = StripeGateway().get_payment_method_details(self.stripe_charge)
        if card_data['status'] == 'FAIL':
            billing = self.organization.organization_billing
            card_data = {
                'status': 'SUCCESS',
                'response': {
                    'brand': billing.card_brand,
                    'final_card_number': billing.final_card_number
                }
            }
        if(card_data['response']['final_card_number']):
            card_data['response']['final_card_number'] = str(card_data['response']['final_card_number'])
            card_data['response']['final_card_number'] = card_data['response']['final_card_number'][len(card_data['response']['final_card_number']) - 2:]
        return card_data

    @property
    def total_invoice_amount(self):
        generic_billing_data = GenericBillingData.get_generic_billing_data_instance()

        contact_count = self.organization_billing_invoice_project.aggregate(
            total_contact_count=Sum("contact_count")
        ).get("total_contact_count")

        amount = generic_billing_data.calculate_active_contacts(contact_count if contact_count else 0)
        integration_cost = float(self.cost_per_whatsapp * self.extra_integration)
        return Decimal(
            float(
                amount + integration_cost
            )
            * float(1 - self.discount / 100)
        ).quantize(Decimal(".01"), decimal.ROUND_HALF_UP)


class InvoiceProject(models.Model):
    class Meta:
        verbose_name = _("organization billing invoice project")

    invoice = models.ForeignKey(
        Invoice, models.CASCADE, related_name="organization_billing_invoice_project"
    )
    project = models.ForeignKey(Project, models.CASCADE)
    amount = models.DecimalField(
        _("amount"), decimal_places=2, max_digits=11, default=0
    )
    contact_count = models.IntegerField(_("active contact count"), default=0)


class GenericBillingData(models.Model):
    _free_active_contacts_limit = models.PositiveIntegerField(_("Free active contacts limit"), default=200)
    _from_1_to_1000 = models.DecimalField(_("From 1 to 1000 active contacts"), decimal_places=3, max_digits=11, default=0.267)
    _from_1001_to_5000 = models.DecimalField(_("From 1001 to 5000 active contacts"), decimal_places=3, max_digits=11, default=0.178)
    _from_5001_to_10000 = models.DecimalField(_("From 5001 to 10000 active contacts"), decimal_places=3, max_digits=11, default=0.167)
    _from_10001_to_30000 = models.DecimalField(_("From 10001 to 30000 active contacts"), decimal_places=3, max_digits=11, default=0.156)
    _from_30001_to_50000 = models.DecimalField(_("From 30001 to 50000 active contacts"), decimal_places=3, max_digits=11, default=0.144)
    _from_50001_to_100000 = models.DecimalField(_("From 50001 to 100000 active contacts"), decimal_places=3, max_digits=11, default=0.140)
    _from_100001_to_250000 = models.DecimalField(_("From 100001 to 250000 active contacts"), decimal_places=3, max_digits=11, default=0.133)
    _from_2500001 = models.DecimalField(_("From 100001 to 250000 active contacts"), decimal_places=3, max_digits=11, default=0.133)

    def __str__(self):
        return f'{self.free_active_contacts_limit}'

    @staticmethod
    def get_generic_billing_data_instance():
        return GenericBillingData.objects.first() if GenericBillingData.objects.all().exists() else GenericBillingData.objects.create()

    @property
    def free_active_contacts_limit(self):
        return self._free_active_contacts_limit

    @free_active_contacts_limit.setter
    def free_active_contacts_limit(self, value):
        self._free_active_contacts_limit = value
        self.save()

    @property
    def precification(self):
        return {
            "currency": "USD",
            "extra_whatsapp_integration": settings.BILLING_COST_PER_WHATSAPP,
            "range": [
                {
                    "from": 1,
                    "to": 1000,
                    "value_per_contact": self._from_1_to_1000,
                },
                {
                    "from": 1001,
                    "to": 5000,
                    "value_per_contact": self._from_1001_to_5000,
                },
                {
                    "from": 5001,
                    "to": 10000,
                    "value_per_contact": self._from_5001_to_10000,
                },
                {
                    "from": 10001,
                    "to": 30000,
                    "value_per_contact": self._from_10001_to_30000,
                },
                {
                    "from": 30001,
                    "to": 50000,
                    "value_per_contact": self._from_30001_to_50000,
                },
                {
                    "from": 50001,
                    "to": 100000,
                    "value_per_contact": self._from_50001_to_100000,
                },
                {
                    "from": 100001,
                    "to": 250000,
                    "value_per_contact": self._from_100001_to_250000,
                },
                {
                    "from": 250001,
                    "to": "infinite",
                    "value_per_contact": self._from_100001_to_250000,
                },
            ]
        }

    def calculate_active_contacts(self, contact_count):
        value_total = 0
        if contact_count <= 1000:
            value_total = 1000 * self._from_1_to_1000
        elif contact_count <= 5000:
            value_total = contact_count * self._from_1001_to_5000
        elif contact_count <= 10000:
            value_total = contact_count * self._from_5001_to_10000
        elif contact_count <= 30000:
            value_total = contact_count * self._from_10001_to_30000
        elif contact_count <= 50000:
            value_total = contact_count * self._from_30001_to_50000
        elif contact_count <= 100000:
            value_total = contact_count * self._from_50001_to_100000
        elif contact_count <= 250000:
            value_total = contact_count * self._from_100001_to_250000
        elif contact_count >= 250000:
            value_total = contact_count * self._from_2500001
        return float(value_total)
