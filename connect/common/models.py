import decimal
import logging
import uuid as uuid4
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.db import models
from django.db.models import Sum
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from timezone_field import TimeZoneField

from connect import utils, billing
from connect.authentication.models import User

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
        send_mail(
            _("Invitation to join organization"),
            render_to_string("authentication/emails/invite_organization.txt"),
            None,
            [email],
            html_message=render_to_string(
                "authentication/emails/invite_organization.html", context
            ),
        )

    def send_email_organization_going_out(self, user_name: str, email: str):
        if not settings.SEND_EMAILS:
            return False
        context = {
            "base_url": settings.BASE_URL,
            "user_name": user_name,
            "organization_name": self.name
        }
        send_mail(
            _(f"You going out of {self.name}"),
            render_to_string("authentication/emails/org_going_out.txt"),
            None,
            [email],
            html_message=render_to_string("authentication/emails/org_going_out.html", context)
        )

    def send_email_organization_removed(self, email: str, user_name: str):
        if not settings.SEND_EMAILS:
            return False
        context = {
            "base_url": settings.BASE_URL,
            "user_name": user_name,
            "orgaization_name": self.name
        }
        send_mail(
            _(f"You have been removed from {self.name}"),
            render_to_string("authentication/emails/org_removed.txt"),
            None,
            [email],
            html_message=render_to_string("authentication/emails/org_removed.html", context)
        )

    def send_email_organization_create(self, email: str, first_name: str):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "webapp_base_url": settings.WEBAPP_BASE_URL,
            "organization_name": self.name,
            "first_name": first_name,
        }
        send_mail(
            _("Organization created!"),
            render_to_string("authentication/emails/organization_create.txt"),
            None,
            [email],
            html_message=render_to_string(
                "authentication/emails/organization_create.html", context
            ),
        )

    def send_email_remove_permission_organization(self, first_name: str, email: str):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "organization_name": self.name,
            "first_name": first_name,
        }
        send_mail(
            _(f"You have been removed from the {self.name}"),
            render_to_string(
                "authentication/emails/remove_permission_organization.txt"
            ),
            None,
            [email],
            html_message=render_to_string(
                "authentication/emails/remove_permission_organization.html", context
            ),
        )

    def send_email_delete_organization(self, first_name: str, email: str):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "organization_name": self.name,
            "first_name": first_name,
        }
        send_mail(
            _(f"{self.name} no longer exists!"),
            render_to_string("authentication/emails/delete_organization.txt"),
            None,
            [email],
            html_message=render_to_string(
                "authentication/emails/delete_organization.html", context
            ),
        )

    def send_email_change_organization_name(self, user_name: str, email: str, organization_previous_name: str,
                                            organization_new_name: str):
        if not settings.SEND_EMAILS:
            return False
        context = {
            "base_url": settings.BASE_URL,
            "user_name": user_name,
            "organization_previous_name": organization_previous_name,
            "organization_new_name": organization_new_name
        }
        send_mail(
            _(f"{organization_previous_name} now it's {organization_new_name}"),
            render_to_string("authentication/emails/change_organization_name.txt"),
            None,
            [email],
            html_message=render_to_string(
                "authentication/emails/change_organization_name.html", context
            ),
        )

    def send_email_access_code(self, email: str, user_name: str, access_code: str):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "access_code": access_code,
            "user_name": user_name,
        }
        send_mail(
            _("You receive an access code to Weni Platform"),
            render_to_string("authentication/emails/access_code.txt"),
            None,
            [email],
            html_message=render_to_string(
                "authentication/emails/access_code.html", context
            ),
        )


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

    def send_email_create_project(self, first_name: str, email: str):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "organization_name": self.organization.name,
            "project_name": self.name,
            "first_name": first_name,
        }
        send_mail(
            _(f"You have been invited to join the {self.name} organization"),
            render_to_string("authentication/emails/project_create.txt"),
            None,
            [email],
            html_message=render_to_string(
                "authentication/emails/project_create.html", context
            ),
        )


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
        default=OrganizationAuthorization.ROLE_NOT_SETTED,
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

    PLAN_CHOICES = [
        (PLAN_FREE, _("free")),
        (PLAN_ENTERPRISE, _("enterprise")),
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
    plan = models.CharField(_("plan"), max_length=10, choices=PLAN_CHOICES)
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
        return gateway.unstore(identification=self.stripe_customer)

    @staticmethod
    def calculate_amount(contact_count: int):
        return Decimal(
            str(utils.calculate_active_contacts(value=contact_count))
        ).quantize(Decimal(".01"), decimal.ROUND_HALF_UP)

    @property
    def currenty_invoice(self):
        contact_count = self.organization.project.aggregate(
            total_contact_count=Sum("contact_count")
        ).get("total_contact_count")

        return {
            "total_contact": contact_count,
            "amount_currenty": Decimal(
                float(
                    float(
                        self.organization.organization_billing.calculate_amount(
                            contact_count=0 if contact_count is None else contact_count
                        )
                    )
                    + settings.BILLING_COST_PER_WHATSAPP
                    * self.organization.extra_integration
                )
                * float(1 - self.fixed_discount / 100)
            ).quantize(Decimal(".01"), decimal.ROUND_HALF_UP),
        }

    def send_email_added_card(self, user_name: str, email: str):
        if not settings.SEND_EMAILS:
            return False
        context = {
            "base_url": settings.BASE_URL,
            "organization_name": self.organization.name,
            "user_name": user_name
        }
        send_mail(
            _(f"Your {self.organization.name} organization's plan has ended "),
            render_to_string("authentication/emails/added_card.txt"),
            None,
            [email],
            html_message=render_to_string("authentication/emails/added_card.html", context)
        )

    def send_email_changed_card(self, user_name: str, email: str):
        if not settings.SEND_EMAILS:
            return False
        context = {
            "base_url": settings.BASE_URL,
            "organization_name": self.organization.name,
            "user_name": user_name
        }
        send_mail(
            _(f"A credit card has been changed to the organization {self.organization.name}"),
            render_to_string("authentication/emails/changed_card.txt"),
            None,
            [email],
            html_message=render_to_string("authentication/emails/changed_card.html", context)
        )

    def send_email_finished_plan(self, user_name: str, email: str):
        if not settings.SEND_EMAILS:
            return False
        context = {
            "base_url": settings.BASE_URL,
            "organization_name": self.organization.name,
            "user_name": user_name
        }
        send_mail(
            _(f"Your {self.organization.name} organization's plan has ended"),
            render_to_string("billing/emails/finished-plan.txt"),
            None,
            [email],
            html_message=render_to_string("billing/emails/finished-plan.html", context)
        )

    def send_email_reactivated_plan(self, user_name: str, email: str):
        if not settings.SEND_EMAILS:
            return False
        context = {
            "base_url": settings.BASE_URL,
            "organization_name": self.organization.name,
            "user_name": user_name
        }
        send_mail(
            _(f" Your {self.organization.name} organization's plan has been reactivated."),
            render_to_string("billing/emails/reactived-plan.txt"),
            None,
            [email],
            html_message=render_to_string("billing/emails/reactived-plan.html", context)
        )

    def send_email_removed_credit_card(self, user_name: str, email: str):
        if not settings.SEND_EMAILS:
            return False
        context = {
            "base_url": settings.BASE_URL,
            "user_name": user_name,
            "org_name": self.organization.name
        }
        send_mail(
            _(f"Your {self.organization.name} organization credit card its removed"),
            render_to_string("billing/emails/removed_card.txt"),
            None,
            [email],
            html_message=render_to_string("billing/emails/removed-card.html", context)
        )

    def send_email_expired_free_plan(self, user_name: str, email: str):
        if not settings.SEND_EMAILS:
            return False
        context = {
            "base_url": settings.BASE_URL,
            "organization_name": self.organization.name,
            "user_name": user_name
        }
        send_mail(
            _(f"The organization {self.organization.name} has already surpassed 200 active contacts"),
            render_to_string("authentication/emails/free-plan-expired.txt"),
            None,
            [email],
            html_message=render_to_string("authentication/emails/free-plan-expired.html", context)
        )

    def send_email_free_plan(self, user_name: str, email: str):
        if not settings.SEND_EMAILS:
            return False
        context = {
            "base_url": settings.BASE_URL,
            "user_name": user_name,
            "org_name": self.organization.name
        }
        send_mail(
            _(f"Your {self.organization.name} organization has the Free Plan"),
            render_to_string("authentication/emails/free_plan.txt"),
            None,
            [email],
            html_message=render_to_string("authentication/emails/free_plan.html", context)
        )


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
    def total_invoice_amount(self):
        amount = self.organization_billing_invoice_project.aggregate(
            total_amount=Sum("amount")
        ).get("total_amount")

        return Decimal(
            float(
                0
                if amount is None
                else amount + self.cost_per_whatsapp * self.extra_integration
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
