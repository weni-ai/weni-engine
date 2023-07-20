import decimal
import logging
import json
import uuid as uuid4
from datetime import timedelta
from decimal import Decimal
import pendulum
from django.conf import settings
from django.core import mail
from django.db import models
from django.db.models import Sum
from django.template.loader import render_to_string
from django.utils import timezone

from django.utils.translation import activate, ugettext_lazy as _

from timezone_field import TimeZoneField

from connect import billing
from connect.authentication.models import User
from connect.billing.gateways.stripe_gateway import StripeGateway
from connect.common.gateways.rocket_gateway import Rocket
from enum import Enum
from celery import current_app
import stripe
from connect.api.v1.internal.intelligence.intelligence_rest_client import (
    IntelligenceRESTClient,
)
from connect.api.v1.internal.flows.flows_rest_client import FlowsRESTClient
# from connect.api.v1.internal.chats.chats_rest_client import ChatsRESTClient
from rest_framework import status
from connect.common.helpers import send_mass_html_mail
from django.db.models import Q

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
        organization_billing__stripe_customer=None,
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
        if organization_billing__stripe_customer:
            new_kwargs.update({"stripe_customer": organization_billing__stripe_customer})

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
    inteligence_organization = models.IntegerField(
        _("inteligence organization id"), null=True, blank=True
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    is_suspended = models.BooleanField(
        default=False, help_text=_("Whether this organization is currently suspended.")
    )
    extra_integration = models.IntegerField(_("Whatsapp Extra Integration"), default=0)
    enforce_2fa = models.BooleanField(_("Only users with 2fa can access the organization"), default=False)
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

    def perform_destroy_ai_organization(self, user_email):
        intelligence_organization = self.inteligence_organization
        ai_client = IntelligenceRESTClient()
        ai_client.delete_organization(
            organization_id=intelligence_organization,
            user_email=user_email,
        )

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
            render_to_string(
                "common/emails/organization/invite_organization.txt", context
            ),
            None,
            [email],
            html_message=render_to_string(
                "common/emails/organization/invite_organization.html", context
            ),
        )
        return mail

    def send_email_organization_going_out(self, user: User):

        if not settings.SEND_EMAILS:
            return False  # pragma: no cover

        context = {
            "base_url": settings.BASE_URL,
            "user_name": user.username,
            "organization_name": self.name,
        }

        if user.language == "pt-br":
            subject = f"Você está deixando a organização {self.name}"
        else:
            subject = _(f"You are leaving {self.name}")

        mail.send_mail(
            subject,
            render_to_string("common/emails/organization/leaving_org.txt", context),
            None,
            [user.email],
            html_message=render_to_string(
                "common/emails/organization/leaving_org.html", context
            ),
        )
        return mail

    def send_email_organization_removed(self, email: str, user_name: str):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "user_name": user_name,
            "organization_name": self.name,
        }
        mail.send_mail(
            _("You have been removed from") + f" {self.name}",
            render_to_string("common/emails/organization/org_removed.txt", context),
            None,
            [email],
            html_message=render_to_string(
                "common/emails/organization/org_removed.html", context
            ),
        )
        return mail

    def send_email_organization_create(self, emails: list = None):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover

        if not emails:
            filter = Q(
                role=OrganizationRole.VIEWER.value) | Q(
                user__email_setup__receive_organization_emails=False
            )
            emails = (
                self.authorizations.exclude(filter)
                .values_list("user__email", "user__username", "user__language")
                .order_by("user__language")
            )

        from_email = None

        context = {
            "base_url": settings.BASE_URL,
            "webapp_base_url": settings.WEBAPP_BASE_URL,
            "organization_name": self.name,
        }

        msg_list = []

        for email in emails:

            username = email[1]
            context["first_name"] = username

            language = email[2]

            if language == "pt-br":
                subject = f"Você acabou de dar vida a {self.name}"
            else:
                subject = _(f"You just gave life to {self.name}")

            message = render_to_string(
                "common/emails/organization/organization_create.txt",
                context,
            )
            html_message = render_to_string(
                "common/emails/organization/organization_create.html",
                context,
            )

            recipient_list = [email[0]]
            msg = (subject, message, html_message, from_email, recipient_list)
            msg_list.append(msg)

        html_mail = send_mass_html_mail(msg_list, fail_silently=False)
        return html_mail

    def send_email_remove_permission_organization(self, first_name: str, email: str):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "organization_name": self.name,
            "first_name": first_name,
        }
        mail.send_mail(
            _("You have been removed from") + f" {self.name}",
            render_to_string(
                "common/emails/organization/remove_permission_organization.txt", context
            ),
            None,
            [email],
            html_message=render_to_string(
                "common/emails/organization/remove_permission_organization.html",
                context,
            ),
        )
        return mail

    def send_email_delete_organization(self, emails: list = None):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover

        if not emails:
            emails = (
                self.authorizations.exclude(
                    role=OrganizationRole.VIEWER.value
                )
                .values_list("user__email", "user__username", "user__language")
                .order_by("user__language")
            )

        from_email = None

        context = {
            "base_url": settings.BASE_URL,
            "webapp_base_url": settings.WEBAPP_BASE_URL,
            "organization_name": self.name,
        }

        msg_list = []

        for email in emails:

            username = email[1]
            context["first_name"] = username

            language = email[2]

            if language == "pt-br":
                subject = f"A organização { self.name } deixou de existir"
            else:
                subject = _(f"The organization { self.name } no longer exists")

            message = render_to_string(
                "common/emails/organization/delete_organization.txt",
                context,
            )
            html_message = render_to_string(
                "common/emails/organization/delete_organization.html",
                context,
            )

            recipient_list = [email[0]]
            msg = (subject, message, html_message, from_email, recipient_list)
            msg_list.append(msg)

        html_mail = send_mass_html_mail(msg_list, fail_silently=False)
        return html_mail

    def send_email_change_organization_name(self, prev_name: str, new_name: str, emails: list = None):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover

        if not emails:
            emails = (
                self.authorizations.exclude(
                    role=OrganizationRole.VIEWER.value
                )
                .values_list("user__email", "user__username", "user__language")
                .order_by("user__language")
            )

        from_email = None

        context = {
            "webapp_billing_url": f"{settings.WEBAPP_BASE_URL}/orgs/{self.uuid}/billing",
            "org_name": self.name,
            "organization_previous_name": prev_name,
            "organization_new_name": new_name,
        }

        msg_list = []

        for email in emails:

            username = email[1]
            context["user_name"] = username

            language = email[2]

            if language == "pt-br":
                subject = f"{prev_name} agora se chama {new_name}!"
            else:
                subject = _(f"{prev_name} is now named {new_name}!")

            message = render_to_string(
                "common/emails/organization/change_organization_name.txt",
                context,
            )
            html_message = render_to_string(
                "common/emails/organization/change_organization_name.html",
                context,
            )

            recipient_list = [email[0]]
            msg = (subject, message, html_message, from_email, recipient_list)
            msg_list.append(msg)

        html_mail = send_mass_html_mail(msg_list, fail_silently=False)
        return html_mail

    def send_email_access_code(self, email: str, user_name: str, access_code: str):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover

        user = User.objects.get(email=email)

        context = {
            "base_url": settings.BASE_URL,
            "access_code": access_code,
            "user_name": user_name,
        }

        mail.send_mail(
            _("You receive an access code to Weni Platform"),
            render_to_string(f"authentication/emails/access_code_{user.language}.txt", context),
            None,
            [email],
            html_message=render_to_string(
                f"authentication/emails/access_code_{user.language}.html", context
            ),
        )
        return mail

    def send_email_permission_change(
        self, user: User, old_permission: str, new_permission: str
    ):

        if not settings.SEND_EMAILS:
            return False  # pragma: no cover

        context = {
            "base_url": settings.BASE_URL,
            "user_name": user.username,
            "old_permission": old_permission,
            "new_permission": new_permission,
            "org_name": self.name,
        }

        activate(user.language)

        if user.language == "pt-br":
            subject = f"Um administrador da organização { self.name } atualizou sua permissão"
        else:
            subject = _(f"An administrator of {self.name } has updated your permission")

        mail.send_mail(
            subject,
            render_to_string(
                "common/emails/organization/permission_change.txt", context
            ),
            None,
            [user.email],
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
        return (
            0 if active_integrations_counter <= 1 else active_integrations_counter - 1
        )

    def set_2fa_required(self, flag: bool):
        self.enforce_2fa = flag
        self.save()

    def get_ai_access_token(self, user_email: str, project):
        ok = False
        data = {}
        intelligence_client = IntelligenceRESTClient()

        try:
            repository_uuid = settings.REPOSITORY_IDS.get(project.template_type)
            access_token = intelligence_client.get_access_token(user_email, repository_uuid)

            if not access_token:
                raise(Exception("access token is None"))

            data = access_token
            ok = True
        except Exception as error:
            logger.error(f"GET AI: {error}")
            data = {
                "data": {"message": "Could not get access token"},
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR
            }
        return ok, data

    def create_ai_organization(self, user_email: str):
        ai_client = IntelligenceRESTClient()
        created = False
        try:
            ai_org = ai_client.create_organization(
                user_email=user_email,
                organization_name=self.name
            )
            data = ai_org.get("id")

            if not data:
                raise(Exception(ai_org))

            self.inteligence_organization = int(ai_org.get("id"))
            self.save(update_fields=["inteligence_organization"])

            created = True

        except Exception as error:
            data = {
                "data": {"message": "Could not create organization in AI module"},
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR
            }
            logger.error(error)

        return created, data


class OrganizationLevelRole(Enum):
    NOTHING, VIEWER, CONTRIBUTOR, ADMIN, FINANCIAL, SUPPORT = list(range(6))


class OrganizationRole(Enum):
    NOT_SETTED, VIEWER, CONTRIBUTOR, ADMIN, FINANCIAL, SUPPORT = list(range(6))


class OrganizationAuthorization(models.Model):
    class Meta:
        verbose_name = _("organization authorization")
        verbose_name_plural = _("organization authorizations")
        unique_together = ["user", "organization"]

    ROLE_CHOICES = [
        (OrganizationRole.NOT_SETTED.value, _("not set")),
        (OrganizationRole.CONTRIBUTOR.value, _("contributor")),
        (OrganizationRole.ADMIN.value, _("admin")),
        (OrganizationRole.VIEWER.value, _("viewer")),
        (OrganizationRole.FINANCIAL.value, _("financial")),
        (OrganizationRole.SUPPORT.value, _("support")),
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
    has_2fa = models.BooleanField(_("2 factor authentication"), default=False)

    def __str__(self):
        return f"{self.organization.name} - {self.user.email}"

    @property
    def level(self):
        if self.role == OrganizationRole.NOT_SETTED.value:
            return OrganizationLevelRole.NOTHING.value

        if self.role == OrganizationRole.CONTRIBUTOR.value:
            return OrganizationLevelRole.CONTRIBUTOR.value

        if self.role == OrganizationRole.ADMIN.value:
            return OrganizationLevelRole.ADMIN.value

        if self.role == OrganizationRole.VIEWER.value:
            return OrganizationLevelRole.VIEWER.value

        if self.role == OrganizationRole.FINANCIAL.value:
            return OrganizationLevelRole.FINANCIAL.value

        if self.role == OrganizationRole.SUPPORT.value:
            return OrganizationLevelRole.SUPPORT.value

    @property
    def can_read(self):
        return self.level in [
            OrganizationLevelRole.FINANCIAL.value,
            OrganizationLevelRole.CONTRIBUTOR.value,
            OrganizationLevelRole.ADMIN.value,
            OrganizationLevelRole.VIEWER.value,
            OrganizationLevelRole.SUPPORT.value,
        ]

    @property
    def can_contribute(self):
        return self.level in [
            OrganizationLevelRole.CONTRIBUTOR.value,
            OrganizationLevelRole.ADMIN.value,
            OrganizationLevelRole.SUPPORT.value,
        ]

    @property
    def can_write(self):
        return self.level in [OrganizationLevelRole.ADMIN.value, OrganizationLevelRole.SUPPORT.value]

    @property
    def is_admin(self):
        return self.level in [OrganizationLevelRole.ADMIN.value, OrganizationLevelRole.SUPPORT.value]

    @property
    def is_financial(self):
        return self.level == OrganizationLevelRole.FINANCIAL.value

    @property
    def can_contribute_billing(self):
        return self.level in [
            OrganizationLevelRole.ADMIN.value,
            OrganizationLevelRole.FINANCIAL.value,
            OrganizationLevelRole.SUPPORT.value,
        ]

    @property
    def role_verbose(self):
        return dict(OrganizationAuthorization.ROLE_CHOICES).get(
            self.role
        )  # pragma: no cover

    def send_new_role_email(self, responsible=None):
        if not settings.SEND_EMAILS:  # pragma: no cover
            return False  # pragma: no cover

    @staticmethod
    def set_2fa(user):
        authorizations = OrganizationAuthorization.objects.filter(user=user)
        for auth in authorizations:
            auth.has_2fa = True
            auth.save()


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

    TYPE_SUPPORT = "support"
    TYPE_LEAD_CAPTURE = "lead_capture"
    TYPE_LEAD_CAPTURE_CHAT_GPT = "lead_capture+chatgpt"
    TYPE_OMIE_LEAD_CAPTURE = "omie_lead_capture"
    TYPE_OMIE_PAYMENT_FINANCIAL = "omie_financial"
    TYPE_OMIE_PAYMENT_FINANCIAL_CHAT_GPT = "omie_financial+chatgpt"
    TYPE_SAC_CHAT_GPT = "sac+chatgpt"

    TEMPLATE_TYPES = (
        (TYPE_SUPPORT, _("support")),
        (TYPE_LEAD_CAPTURE, _("lead capture")),
        (TYPE_LEAD_CAPTURE_CHAT_GPT, _("lead_capture+chatgpt")),
        (TYPE_OMIE_LEAD_CAPTURE, "omie_lead_capture"),
        (TYPE_OMIE_PAYMENT_FINANCIAL, "omie_financial"),
        (TYPE_OMIE_PAYMENT_FINANCIAL_CHAT_GPT, "omie_financial+chatgpt"),
        (TYPE_SAC_CHAT_GPT, "sac+chatgpt"),
    )

    HAS_GLOBALS = [TYPE_OMIE_LEAD_CAPTURE, TYPE_OMIE_PAYMENT_FINANCIAL, TYPE_OMIE_PAYMENT_FINANCIAL_CHAT_GPT, TYPE_LEAD_CAPTURE_CHAT_GPT, TYPE_SAC_CHAT_GPT]
    HAS_CHATS = [TYPE_OMIE_LEAD_CAPTURE, TYPE_OMIE_PAYMENT_FINANCIAL, TYPE_OMIE_PAYMENT_FINANCIAL_CHAT_GPT, TYPE_SUPPORT, TYPE_SAC_CHAT_GPT]

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
    flow_organization = models.UUIDField(_("flow identification UUID"), unique=True, null=True, blank=True)
    flow_id = models.PositiveIntegerField(
        _("flow identification ID"), unique=True, null=True
    )
    inteligence_count = models.IntegerField(_("Intelligence count"), default=0)
    flow_count = models.IntegerField(_("Flows count"), default=0)
    contact_count = models.IntegerField(_("Contacts count"), default=0)
    total_contact_count = models.IntegerField(
        _("Contacts count of all time"), default=0
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    extra_active_integration = models.IntegerField(
        _("Whatsapp Integrations"), default=0
    )
    is_template = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="projects",
        blank=True,
        null=True,
    )
    template_type = models.CharField(
        verbose_name=_("Template type"),
        max_length=30,
        choices=TEMPLATE_TYPES,
        help_text=_("Project template type"),
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.uuid} - Project: {self.name} - Org: {self.organization.name}"

    def get_user_authorization(self, user, **kwargs):
        if user.is_anonymous:
            return ProjectAuthorization(project=self)  # pragma: no cover
        get, created = ProjectAuthorization.objects.get_or_create(
            user=user,
            project=self,
            organization_authorization=self.organization.get_user_authorization(user),
            **kwargs,
        )
        return get

    def project_search(self, text: str):
        """Searches for project in flows and intelligence"""

        flows_client = FlowsRESTClient()
        intelligence_client = IntelligenceRESTClient()

        flows_result = flows_client.get_project_flows(
            project_uuid=self.uuid, flow_name=text
        )
        intelligence_result = intelligence_client.get_organization_intelligences(
            intelligence_name=text,
            organization_id=self.organization.inteligence_organization,
        )

        return {"flow": flows_result, "intelligence": intelligence_result}

    def perform_destroy_flows_project(self, user_email: str):
        project_uuid = self.uuid

        current_app.send_task("delete_project", args=[project_uuid, user_email])

    def send_email_create_project(self, emails: list = None):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover

        if not emails:
            filter = Q(
                role=OrganizationRole.VIEWER.value) | Q(
                user__email_setup__receive_project_emails=False
            )
            emails = (
                self.project_authorizations.exclude(filter)
                .values_list("user__email", "user__username", "user__language")
                .order_by("user__language")
            )

        from_email = None
        msg_list = []

        context = {
            "base_url": settings.BASE_URL,
            "organization_name": self.organization.name,
            "project_name": self.name,
        }

        for email in emails:

            username = email[1]
            context["first_name"] = username

            language = email[2]

            if language == "pt-br":
                subject = "Seu projeto foi criado com sucesso!"
            else:
                subject = _("Your project has been successfully created!")

            message = render_to_string(
                "common/emails/project/project_create.txt",
                context,
            )
            html_message = render_to_string(
                "common/emails/project/project_create.html",
                context,
            )

            recipient_list = [email[0]]
            msg = (subject, message, html_message, from_email, recipient_list)
            msg_list.append(msg)

        html_mail = send_mass_html_mail(msg_list, fail_silently=False)
        return html_mail

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

    def create_classifier(self, authorization, template_type: str, access_token: str):
        flow_instance = FlowsRESTClient()
        created = False

        classifier_name = {
            "lead_capture": "Farewell & Greetings",
            "lead_capture+chatgpt": "Farewell & Greetings",
            "support": "Binary Answers",
            "omie": "OMIE",
            "omie_financial": "Cristal - Assistente Financeiro",
            "omie_lead_capture": "Cristal - Assistente Financeiro",
            "omie_financial+chatgpt": "Cristal - Assistente Financeiro",
            "sac+chatgpt": "Cristal - Assistente Financeiro",
        }

        try:
            response = flow_instance.create_classifier(
                project_uuid=str(self.flow_organization),
                user_email=authorization.user.email,
                classifier_type="bothub",
                classifier_name=classifier_name.get(template_type),
                access_token=access_token,
            )

            status_code = response.get("status")

            if status_code not in range(200, 299):
                raise(Exception(f"Status: {status_code}"))

            created = True
            data = response.get("data").get("uuid")

        except Exception as error:
            logger.error(f"Could not create classifier {error}")
            data = {
                "data": {"message": "Could not create classifier"},
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR
            }

        return created, data

    def create_chats_project(self):
        from connect.api.v1.internal.chats.chats_rest_client import ChatsRESTClient  # to avoid circular import
        created = False
        chats_client = ChatsRESTClient()
        try:
            chats_response = chats_client.create_chat_project(
                project_uuid=str(self.uuid),
                project_name=self.name,
                date_format=self.date_format,
                timezone=str(self.timezone),
                is_template=True,
                user_email=self.created_by.email
            )
            chats_response = json.loads(chats_response.text)
            data = chats_response
            created = True
        except Exception as error:
            logger.error(f"Could not create chats {error}")
            data = {
                "data": {"message": "Could not create chats"},
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR
            }
        return created, data

    def create_flows(self, classifier_uuid: str):
        data = {}
        chats_response = {}
        created = False

        flow_instance = FlowsRESTClient()
        has_chats = self.template_type in Project.HAS_CHATS

        if has_chats:
            chats_created, chats_response = self.create_chats_project()
            if not chats_created:
                return chats_created, chats_response

        try:
            flows = flow_instance.create_flows(
                str(self.uuid),
                str(classifier_uuid),
                self.template_type,
                ticketer=chats_response.get("ticketer"),
                queue=chats_response.get("queue"),
            )
            data = json.loads(flows.get("data"))
            created = True
        except Exception as error:
            logger.error(f"Could not create flow {error}")
            data.update(
                {
                    "data": {"message": "Could not create flow"},
                    "status": status.HTTP_500_INTERNAL_SERVER_ERROR
                }
            )
        return created, data

    def whatsapp_demo_integration(self, token):
        from connect.api.v1.internal.integrations.integrations_rest_client import IntegrationsRESTClient
        created = False
        integrations_client = IntegrationsRESTClient()
        data = {}
        try:
            response = integrations_client.whatsapp_demo_integration(str(self.uuid), token=token)
            created = True
            data = response
        except Exception as error:
            logger.error(f"Could not integrate Whatsapp demo {error}")
            data = {
                "data": {"message": "Could not integrate Whatsapp demo"},
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
            }
        return created, data

    def send_email_invite_project(self, email):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "webapp_base_url": settings.WEBAPP_BASE_URL,
            "organization_name": self.organization.name,
            "project_name": self.name,
        }
        mail.send_mail(
            _("Invitation to join organization"),
            render_to_string(
                "common/emails/project/invite_project.txt", context
            ),
            None,
            [email],
            html_message=render_to_string(
                "common/emails/project/invite_project.html", context
            ),
        )
        return mail


class OpenedProject(models.Model):
    day = models.DateTimeField(_("Day"))
    project = models.ForeignKey(
        Project, models.CASCADE, related_name="opened_project"
    )
    user = models.ForeignKey(User, models.CASCADE, related_name="user")


class RocketRole(Enum):
    NOT_SETTED, USER, ADMIN, AGENT, SERVICE_MANAGER = list(range(5))


class RocketRoleLevel(Enum):
    NOTHING, USER, ADMIN, AGENT, SERVICE_MANAGER = list(range(5))


class RocketAuthorization(models.Model):
    ROLE_CHOICES = [
        (RocketRole.NOT_SETTED.value, _("not set")),
        (RocketRole.USER.value, _("user")),
        (RocketRole.ADMIN.value, _("admin")),
        (RocketRole.AGENT.value, _("agent")),
        (RocketRole.SERVICE_MANAGER.value, _("service manager")),
    ]

    role = models.PositiveIntegerField(
        _("role"), choices=ROLE_CHOICES, default=RocketRole.NOT_SETTED.value
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    @property
    def level(self):
        if self.role == RocketRole.AGENT.value:
            return RocketRoleLevel.AGENT.value
        elif self.role == RocketRole.SERVICE_MANAGER.value:
            return RocketRoleLevel.SERVICE_MANAGER.value
        return RocketRoleLevel.NOTHING.value

    def update_rocket_permission(self):  # pragma: no cover
        rocket = (
            self.projectauthorization_set.first()
            .project.service_status.get(service__service_type="type_service_chat")
            .service
        )

        rocket_user = self.projectauthorization_set.first().user.email.split("@")[0]
        handler = Rocket(rocket)

        user_exists = handler.get_user(rocket_user)

        if user_exists["success"]:
            username = user_exists["user"]["username"]
        else:
            response = handler.create_user(
                self.projectauthorization_set.first().user.first_name,
                self.projectauthorization_set.first().user.email,
            )
            username = response["user"]["username"]

        request = handler.add_user_role(self.role, username)
        return request


class ChatsRole(Enum):
    NOT_SETTED, USER, ADMIN, AGENT, SERVICE_MANAGER = list(range(5))


class ChatsRoleLevel(Enum):
    NOTHING, USER, ADMIN, AGENT, SERVICE_MANAGER = list(range(5))


class ChatsAuthorization(models.Model):
    ROLE_CHOICES = [
        (ChatsRole.NOT_SETTED.value, _("not set")),
        (ChatsRole.USER.value, _("user")),
        (ChatsRole.AGENT.value, _("agent")),
        (ChatsRole.ADMIN.value, _("admin")),
        (ChatsRole.SERVICE_MANAGER.value, _("service_manager")),
    ]
    role = models.PositiveIntegerField(
        _("role"), choices=ROLE_CHOICES, default=ChatsRole.NOT_SETTED.value
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    @property
    def level(self):
        if self.role == ChatsRole.AGENT.value:
            return ChatsRoleLevel.AGENT.value
        elif self.role == ChatsRole.SERVICE_MANAGER.value:
            return ChatsRoleLevel.SERVICE_MANAGER.value
        elif self.role == ChatsRole.ADMIN.value:
            return ChatsRoleLevel.ADMIN.value
        return ChatsRoleLevel.NOTHING.value


class ProjectRole(Enum):
    NOT_SETTED, VIEWER, CONTRIBUTOR, MODERATOR, SUPPORT, CHAT_USER = list(range(6))


class ProjectRoleLevel(Enum):
    NOTHING, VIEWER, CONTRIBUTOR, MODERATOR, SUPPORT, CHAT_USER = list(range(6))


class ProjectAuthorization(models.Model):
    class Meta:
        unique_together = ["user", "project"]

    ROLE_CHOICES = [
        (ProjectRole.NOT_SETTED.value, _("not set")),
        (ProjectRole.VIEWER.value, _("viewer")),
        (ProjectRole.CONTRIBUTOR.value, _("contributor")),
        (ProjectRole.MODERATOR.value, _("moderator")),
        (ProjectRole.SUPPORT.value, _("support")),
        (ProjectRole.CHAT_USER.value, _("Chat user")),
    ]
    uuid = models.UUIDField(
        _("UUID"), primary_key=True, default=uuid4.uuid4, editable=False
    )
    user = models.ForeignKey(
        User, models.CASCADE, related_name="project_authorizations_user"
    )
    project = models.ForeignKey(
        Project, models.CASCADE, related_name="project_authorizations"
    )
    organization_authorization = models.ForeignKey(
        OrganizationAuthorization, models.CASCADE
    )
    rocket_authorization = models.ForeignKey(
        RocketAuthorization, models.CASCADE, null=True, default=None
    )
    chats_authorization = models.ForeignKey(
        ChatsAuthorization, models.CASCADE, null=True, default=None
    )
    role = models.PositiveIntegerField(
        _("role"), choices=ROLE_CHOICES, default=ProjectRole.NOT_SETTED.value
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    def __str__(self):
        return f"{self.project.name} - {self.user.email}"

    @property
    def level(self):
        if self.role == ProjectRole.MODERATOR.value:
            return ProjectRoleLevel.MODERATOR.value
        elif self.role == ProjectRole.CONTRIBUTOR.value:
            return ProjectRoleLevel.CONTRIBUTOR.value
        elif self.role == ProjectRole.VIEWER.value:
            return ProjectRoleLevel.VIEWER.value
        elif self.role == ProjectRole.SUPPORT.value:
            return ProjectRoleLevel.SUPPORT.value

    @property
    def is_moderator(self):
        return self.level in [ProjectRoleLevel.MODERATOR.value, ProjectRoleLevel.SUPPORT.value]

    @property
    def can_write(self):
        return self.level in [ProjectRoleLevel.MODERATOR.value, ProjectRoleLevel.SUPPORT.value]

    @property
    def can_read(self):
        return self.level in [
            ProjectRoleLevel.MODERATOR.value,
            ProjectRoleLevel.CONTRIBUTOR.value,
            ProjectRoleLevel.VIEWER.value,
            ProjectRoleLevel.SUPPORT.value,
            ProjectRoleLevel.CHAT_USER.value
        ]

    @property
    def can_contribute(self):
        return self.level in [
            ProjectRoleLevel.MODERATOR.value,
            ProjectRoleLevel.CONTRIBUTOR.value,
            ProjectRoleLevel.SUPPORT.value,
        ]


class RequestRocketPermission(models.Model):
    email = models.EmailField(_("email"))
    role = models.PositiveIntegerField(
        _("role"),
        choices=RocketAuthorization.ROLE_CHOICES,
        default=RocketRole.NOT_SETTED.value,
    )
    project = models.ForeignKey(Project, models.CASCADE)
    created_by = models.ForeignKey(User, models.CASCADE)


class RequestChatsPermission(models.Model):
    email = models.EmailField(_("email"))
    role = models.PositiveIntegerField(
        _("role"),
        choices=ChatsAuthorization.ROLE_CHOICES,
        default=ChatsRole.NOT_SETTED.value,
    )
    project = models.ForeignKey(Project, models.CASCADE)
    created_by = models.ForeignKey(User, models.CASCADE)


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


class RequestPermissionProject(models.Model):
    class Meta:
        verbose_name = _("request permission project")
        unique_together = ["email", "project"]

    email = models.EmailField(_("email"))
    project = models.ForeignKey(Project, models.CASCADE)
    role = models.PositiveIntegerField(
        _("role"),
        choices=ProjectAuthorization.ROLE_CHOICES,
        default=ProjectRole.NOT_SETTED.value,
    )
    created_by = models.ForeignKey(User, models.CASCADE)

    def __str__(self):
        return f"{self.project.name}, {self.role}, <{self.email}>"


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
    PLAN_TRIAL = "trial"
    PLAN_START = "start"
    PLAN_SCALE = "scale"
    PLAN_ADVANCED = "advanced"
    PLAN_ENTERPRISE = "enterprise"
    PLAN_CUSTOM = "custom"

    PLAN_CHOICES = [
        (PLAN_FREE, _("free")),
        (PLAN_TRIAL, _("trial")),
        (PLAN_START, _("start")),
        (PLAN_SCALE, _("scale")),
        (PLAN_ADVANCED, _("advanced")),
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
        verbose_name="Personal Identification Number",
        null=True,
        blank=True,
        max_length=50,
    )

    additional_billing_information = models.CharField(
        verbose_name=_("Additional billing information"),
        null=True,
        blank=True,
        max_length=250,
    )

    card_is_valid = models.BooleanField(_("Card is valid"), default=False)
    trial_end_date = models.DateTimeField(_("Trial end date"), null=True, blank=True)

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None, **kwargs):
        _adding = self._state.adding
        if _adding or kwargs.get("change_plan"):
            from connect import billing

            card = billing.get_gateway("stripe")

            card_data = card.get_card_data(self.stripe_customer)

            if card_data.get("status") == "SUCCESS" and len(card_data["response"]) > 0:
                card_info = card_data["response"][0]
                self.stripe_configured_card = True
                self.final_card_number = card_info.get("last2")
                self.cardholder_name = card_info.get("cardholder_name")
                self.card_brand = card_info.get("brand")
                self.card_expiration_date = card_info.get("card_expiration_date")

            if _adding and self.plan == self.PLAN_TRIAL:
                self.trial_end_date = pendulum.now().end_of("day").add(months=1)
            else:
                # Create invoice for charges
                stripe.api_key = settings.BILLING_SETTINGS.get("stripe", {}).get(
                    "API_KEY"
                )

                customer = self.stripe_customer

                if settings.TESTING:
                    charges = {"data": [{"id": "ch_teste", "amount": 39000}]}

                else:
                    charges = stripe.PaymentIntent.list(customer=customer)

                Invoice.objects.create(
                    organization=self.organization,
                    stripe_charge=charges["data"][0]["id"],
                    notes="Plan setup" if _adding else "Upgrade Plan",
                    paid_date=pendulum.now(),
                    due_date=pendulum.now(),
                    payment_status=Invoice.PAYMENT_STATUS_PAID,
                    payment_method='credit_card',
                    invoice_amount=(charges["data"][0]["amount"] / 100)
                )
                for project in self.organization.project.all():  # pragma: no cover
                    current_app.send_task(
                        name="update_suspend_project", args=[project.uuid, False]
                    )

        return super().save(force_insert, force_update, using, update_fields)

    @staticmethod
    def plan_info(plan):

        plans_list = [plan[0] for plan in BillingPlan.PLAN_CHOICES]

        if plan in plans_list:

            if plan == BillingPlan.PLAN_TRIAL:
                price = settings.PLAN_TRIAL_PRICE
                limit = settings.PLAN_TRIAL_LIMIT

            elif plan == BillingPlan.PLAN_START:
                price = settings.PLAN_START_PRICE
                limit = settings.PLAN_START_LIMIT

            elif plan == BillingPlan.PLAN_SCALE:
                price = settings.PLAN_SCALE_PRICE
                limit = settings.PLAN_SCALE_LIMIT

            elif plan == BillingPlan.PLAN_ADVANCED:
                price = settings.PLAN_ADVANCED_PRICE
                limit = settings.PLAN_ADVANCED_LIMIT

            elif plan == BillingPlan.PLAN_ENTERPRISE:
                price = settings.PLAN_ENTERPRISE_PRICE
                limit = settings.PLAN_ENTERPRISE_LIMIT
            else:
                return {"valid": False}

            return {"price": price, "limit": limit, "valid": True}

        return {"valid": False}

    @property
    def plan_limit(self):
        return BillingPlan.plan_info(self.plan)["limit"]

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
        if unstore["status"] == "SUCCESS":
            self.card_brand = None
            self.card_expiration_date = None
            self.final_card_number = None
            self.cardholder_name = None
            self.stripe_configured_card = False
            self.save()
            return True
        return False

    @staticmethod  # PRECISA MUDAR
    def calculate_amount(contact_count: int):
        precification = GenericBillingData.get_generic_billing_data_instance()
        return Decimal(
            str(precification.calculate_active_contacts(contact_count=contact_count))
        ).quantize(Decimal(".01"), decimal.ROUND_HALF_UP)

    @property
    def is_card_valid(self):  # pragma: no cover
        if self.plan != self.PLAN_TRIAL:
            return self.card_is_valid

    @property
    def _currenty_invoice(self):
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
                    )
                    + (
                        settings.BILLING_COST_PER_WHATSAPP
                        * self.organization.extra_integration
                    )
                )
                * float(1 - self.fixed_discount / 100)
            ).quantize(Decimal(".01"), decimal.ROUND_HALF_UP)

        return {"total_contact": contact_count, "amount_currenty": amount_currenty}

    @property
    def currenty_invoice(self):
        # Total contacts of the organization
        contact_count = self.organization.project.aggregate(
            total_contact_count=Sum("contact_count")
        ).get("total_contact_count")

        if self.plan != self.PLAN_ENTERPRISE:
            amount_currenty = Decimal(
                BillingPlan.plan_info(self.plan)["price"]
                + (settings.BILLING_COST_PER_WHATSAPP * self.organization.extra_integration)
            ).quantize(Decimal(".01"), decimal.ROUND_HALF_UP)
        else:
            amount_currenty = BillingPlan.plan_info(self.plan)["price"]

        return {"total_contact": contact_count, "amount_currenty": amount_currenty}

    def change_plan(self, plan):
        _is_valid = False
        for choice in self.PLAN_CHOICES:
            if plan in choice:
                _is_valid = True
                self.plan = choice[0]
                self.contract_on = pendulum.now()
                self.next_due_date = pendulum.now().add(months=1)
                self.organization.is_suspended = False
                self.organization.save(update_fields=["is_suspended"])
                self.is_active = True
                self.save(update_fields=["plan", "contract_on", "next_due_date", "is_active"], change_plan=True)
                # send mail here
                break
        return _is_valid

    def add_additional_information(self, data: dict):
        count = 0
        if not (data["additional_info"] is None):
            self.additional_billing_information = data["additional_info"]
            count += 1
        if not (data["personal_identification_number"] is None):
            self.personal_identification_number = data["personal_identification_number"]
            count += 1
        if not (data["extra_integration"] is None):
            self.organization.extra_integration = data["extra_integration"]
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
            "user_name": user_name,
        }
        mail.send_mail(
            _("A credit card has been added to the organization")
            + f" {self.organization.name}",
            render_to_string("billing/emails/added_card.txt", context),
            None,
            email,
            html_message=render_to_string("billing/emails/added_card.html", context),
        )
        return mail

    def send_email_changed_card(self, user_name: str, email: str):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "organization_name": self.organization.name,
            "user_name": user_name,
        }
        mail.send_mail(
            _("A credit card has been updated in the organization")
            + f" {self.organization.name}",
            render_to_string("billing/emails/changed_card.txt", context),
            None,
            email,
            html_message=render_to_string("billing/emails/changed_card.html", context),
        )
        return mail

    def send_email_finished_plan(self, user_name: str, email: list):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "organization_name": self.organization.name,
            "user_name": user_name,
        }
        from_email = None
        msg_list = []
        for user_email in email:

            language_code = User.objects.get(email=user_email).language
            activate(language_code)
            message = render_to_string(
                "billing/emails/finished-plan.txt", context
            )
            html_message = render_to_string(
                "billing/emails/finished-plan.html", context
            )
            if language_code == "en-us":
                subject = _(
                    "Your organization's plan has ended"
                )
            else:
                subject = _(
                    "O plano da sua organização foi encerrado."
                )

            recipient_list = [user_email]
            msg = (subject, message, html_message, from_email, recipient_list)
            msg_list.append(msg)

        html_mail = send_mass_html_mail(msg_list, fail_silently=False)
        return html_mail

    def send_email_reactivated_plan(self, user_name: str, email: list):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "organization_name": self.organization.name,
            "user_name": user_name,
        }
        from_email = None
        msg_list = []
        for user_email in email:

            language_code = User.objects.get(email=user_email).language
            activate(language_code)
            message = render_to_string(
                "billing/emails/reactived-plan.txt", context
            )
            html_message = render_to_string(
                "billing/emails/reactived-plan.html", context
            )
            if language_code == "en-us":
                subject = _(
                    "Your organization's plan has been reactivated."
                )
            else:
                subject = _(
                    "O plano da sua organização foi reativado."
                )

            recipient_list = [user_email]
            msg = (subject, message, html_message, from_email, recipient_list)
            msg_list.append(msg)

        html_mail = send_mass_html_mail(msg_list, fail_silently=False)
        return html_mail

    def send_email_removed_credit_card(self, user_name: str, email: list):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "user_name": user_name,
            "org_name": self.organization.name,
        }
        from_email = None
        msg_list = []
        for user_email in email:

            language_code = User.objects.get(email=user_email).language
            activate(language_code)
            message = render_to_string(
                "billing/emails/removed_card.txt", context
            )
            html_message = render_to_string(
                "billing/emails/removed_card.html", context
            )
            if language_code == "en-us":
                subject = _(
                    "Your organization's credit card was removed"
                )
            else:
                subject = _(
                    "O cartão de crédito vinculado a sua organização foi removido"
                )

            recipient_list = [user_email]
            msg = (subject, message, html_message, from_email, recipient_list)
            msg_list.append(msg)

        html_mail = send_mass_html_mail(msg_list, fail_silently=False)
        return html_mail

    def send_email_expired_free_plan(self, user_name: str, email: list):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "organization_name": self.organization.name,
            "user_name": user_name,
        }
        mail.send_mail(
            _("Your organization")
            + f" {self.organization.name} "
            + _("has already surpassed 200 active contacts"),
            render_to_string("billing/emails/free-plan-expired.txt", context),
            None,
            email,
            html_message=render_to_string(
                "billing/emails/free-plan-expired.html", context
            ),
        )
        return mail

    def send_email_chosen_plan(self, user_name: str, email: str, plan: str):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "user_name": user_name,
            "org_name": self.organization.name,
            "plan": plan,
        }
        mail.send_mail(
            _("Your organization")
            + f" {self.organization.name} "
            + _("has the plan")
            + ": "
            + f"{plan.title()}",
            render_to_string("billing/emails/free_plan.txt", context),
            None,
            [email],
            html_message=render_to_string("billing/emails/free_plan.html", context),
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
            "actual_plan": self.plan,
        }
        mail.send_mail(
            _("Your organization's plan has been updated"),
            render_to_string("billing/emails/changed-plan.txt", context),
            None,
            email,
            html_message=render_to_string("billing/emails/changed-plan.html", context),
        )
        return mail

    def send_email_trial_plan_expired_due_time_limit(self, emails: list = None):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover

        if not emails:
            emails = (
                self.organization.authorizations.exclude(
                    role=OrganizationRole.VIEWER.value
                )
                .values_list("user__email", "user__username", "user__language")
                .order_by("user__language")
            )

        subject = _("Your trial plan has expired")
        from_email = None

        context = {
            "webapp_billing_url": f"{settings.WEBAPP_BASE_URL}/orgs/{self.organization.uuid}/billing",
            "org_name": self.organization.name,
        }

        msg_list = []
        for email in emails:

            language_code = email[2]
            username = email[1]
            context["user_name"] = username
            message = render_to_string(
                "billing/emails/trial_plan_expired_due_time_limit_en.txt", context
            )
            html_message = render_to_string(
                "billing/emails/trial_plan_expired_due_time_limit_en.html", context
            )
            if language_code == "en-us":
                subject = _("Your trial plan has expired")
            else:
                subject = "Seu plano Trial expirou"

            recipient_list = [email[0]]
            msg = (subject, message, html_message, from_email, recipient_list)
            msg_list.append(msg)

        html_mail = send_mass_html_mail(msg_list, fail_silently=False)
        return html_mail

    def send_email_plan_expired_due_attendance_limit(self, emails: list = None):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover

        if not emails:
            emails = (
                self.organization.authorizations.exclude(
                    role=OrganizationRole.VIEWER.value
                )
                .values_list("user__email", "user__username", "user__language")
                .order_by("user__language")
            )

        from_email = None
        msg_list = []

        context = {
            "webapp_billing_url": f"{settings.WEBAPP_BASE_URL}/orgs/{self.organization.uuid}/billing",
            "plan": self.plan,
            "plan_limit": self.plan_limit,
            "org_name": self.organization.name,
        }

        for email in emails:

            language_code = email[2]
            activate(language_code)
            username = email[1]
            context["user_name"] = username
            html_message = render_to_string(
                "billing/emails/plan_expired_due_attendence_limit_en.html", context
            )
            message = render_to_string(
                "billing/emails/plan_expired_due_attendence_limit_en.txt", context
            )
            if language_code == "en-us":
                subject = _(f"You reached {self.plan_limit} attendances")
            else:
                subject = _(f"Você atingiu {self.plan_limit} atendimentos")

            recipient_list = [email[0]]
            msg = (subject, message, html_message, from_email, recipient_list)
            msg_list.append(msg)

        html_mail = send_mass_html_mail(msg_list, fail_silently=False)

        return html_mail

    def send_email_plan_is_about_to_expire(self, emails: list = None):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover

        if not emails:
            emails = (
                self.organization.authorizations.exclude(
                    role=OrganizationRole.VIEWER.value
                )
                .values_list("user__email", "user__username", "user__language")
                .order_by("user__language")
            )

        from_email = None
        msg_list = []

        context = {
            "limit": self.plan_limit,
            "webapp_billing_url": f"{settings.WEBAPP_BASE_URL}/orgs/{self.organization.uuid}/billing",
            "org_name": self.organization.name,
        }

        for email in emails:

            username = email[1]
            language_code = email[2]
            activate(language_code)
            context["user_name"] = username
            message = render_to_string(
                "billing/emails/plan_is_about_to_expire_en.txt", context
            )
            html_message = render_to_string(
                "billing/emails/plan_is_about_to_expire_en.html", context
            )
            if language_code == "en-us":
                subject = _(
                    f"Your organization is close to {self.plan_limit} attendances"
                )
            else:
                subject = _(
                    f"Sua organização estã proxima de {self.plan_limit} atendimentos"
                )

            recipient_list = [email[0]]
            msg = (subject, message, html_message, from_email, recipient_list)
            msg_list.append(msg)

        html_mail = send_mass_html_mail(msg_list, fail_silently=False)
        return html_mail

    def send_email_end_trial(self, email: list):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {
            "base_url": settings.BASE_URL,
            "webapp_base_url": settings.WEBAPP_BASE_URL,
            "organization_name": self.organization.name,
        }
        mail.send_mail(
            _("Your trial period has ended"),
            render_to_string("common/emails/organization/end_trial.txt", context),
            None,
            email,
            html_message=render_to_string(
                "common/emails/organization/end_trial.html", context
            ),
        )
        return mail

    def end_trial_period(self):
        newsletter = Newsletter.objects.create()

        NewsletterOrganization.objects.create(
            newsletter=newsletter,
            title="trial-ended",
            description=f"Your trial period of the organization {self.organization.name}, has ended, do an upgrade.",
            organization=self.organization
        )

        self.is_active = False
        self.save(update_fields=["is_active"])
        self.organization.is_suspended = True
        self.organization.save(update_fields=["is_suspended"])
        for project in self.organization.project.all():
            current_app.send_task(  # pragma: no cover
                name="update_suspend_project", args=[project.uuid, True]
            )

    @property
    def days_till_trial_end(self):
        if self.plan == BillingPlan.PLAN_TRIAL:
            today = pendulum.now()
            trial_end = pendulum.instance(self.trial_end_date)
            return today.diff(trial_end, False).in_days()


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
    invoice_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True)

    @property
    def card_data(self):
        card_data = StripeGateway().get_payment_method_details(self.stripe_charge)
        if card_data["status"] == "FAIL":
            billing = self.organization.organization_billing
            card_data = {
                "status": "SUCCESS",
                "response": {
                    "brand": billing.card_brand,
                    "final_card_number": billing.final_card_number,
                },
            }
        if card_data["response"]["final_card_number"]:
            card_data["response"]["final_card_number"] = str(
                card_data["response"]["final_card_number"]
            )
            card_data["response"]["final_card_number"] = card_data["response"][
                "final_card_number"
            ][len(card_data["response"]["final_card_number"]) - 2 :]
        return card_data

    @property
    def total_invoice_amount(self):
        return self.invoice_amount


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
    _free_active_contacts_limit = models.PositiveIntegerField(
        _("Free active contacts limit"), default=200
    )
    _from_1_to_1000 = models.DecimalField(
        _("From 1 to 1000 active contacts"),
        decimal_places=3,
        max_digits=11,
        default=0.267,
    )
    _from_1001_to_5000 = models.DecimalField(
        _("From 1001 to 5000 active contacts"),
        decimal_places=3,
        max_digits=11,
        default=0.178,
    )
    _from_5001_to_10000 = models.DecimalField(
        _("From 5001 to 10000 active contacts"),
        decimal_places=3,
        max_digits=11,
        default=0.167,
    )
    _from_10001_to_30000 = models.DecimalField(
        _("From 10001 to 30000 active contacts"),
        decimal_places=3,
        max_digits=11,
        default=0.156,
    )
    _from_30001_to_50000 = models.DecimalField(
        _("From 30001 to 50000 active contacts"),
        decimal_places=3,
        max_digits=11,
        default=0.144,
    )
    _from_50001_to_100000 = models.DecimalField(
        _("From 50001 to 100000 active contacts"),
        decimal_places=3,
        max_digits=11,
        default=0.140,
    )
    _from_100001_to_250000 = models.DecimalField(
        _("From 100001 to 250000 active contacts"),
        decimal_places=3,
        max_digits=11,
        default=0.133,
    )
    _from_2500001 = models.DecimalField(
        _("From 100001 to 250000 active contacts"),
        decimal_places=3,
        max_digits=11,
        default=0.133,
    )

    def __str__(self):
        return f"{self.free_active_contacts_limit}"

    @staticmethod
    def get_generic_billing_data_instance():
        return (
            GenericBillingData.objects.first()
            if GenericBillingData.objects.all().exists()
            else GenericBillingData.objects.create()
        )

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
            "currency": settings.DEFAULT_CURRENCY,
            "extra_whatsapp_integration": settings.BILLING_COST_PER_WHATSAPP,
            "plans": {
                "trial": {
                    "limit": settings.PLAN_TRIAL_LIMIT,
                    "price": settings.PLAN_TRIAL_PRICE,
                },
                "start": {
                    "limit": settings.PLAN_START_LIMIT,
                    "price": settings.PLAN_START_PRICE,
                },
                "scale": {
                    "limit": settings.PLAN_SCALE_LIMIT,
                    "price": settings.PLAN_SCALE_PRICE,
                },
                "advanced": {
                    "limit": settings.PLAN_ADVANCED_LIMIT,
                    "price": settings.PLAN_ADVANCED_PRICE,
                },
                "enterprise": {
                    "limit": settings.PLAN_ENTERPRISE_LIMIT,
                    "price": settings.PLAN_ENTERPRISE_PRICE,
                },
            },
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


class TemplateProject(models.Model):
    uuid = models.UUIDField(
        _("UUID"), primary_key=True, default=uuid4.uuid4, editable=False
    )
    project = models.ForeignKey(
        Project, models.CASCADE, related_name="template_project"
    )
    wa_demo_token = models.CharField(max_length=30)
    classifier_uuid = models.UUIDField(_("UUID"), default=uuid4.uuid4)
    first_access = models.BooleanField(default=True)
    authorization = models.ForeignKey(ProjectAuthorization, on_delete=models.CASCADE)
    flow_uuid = models.UUIDField(_("UUID"), default=uuid4.uuid4)
    redirect_url = models.URLField(null=True)

    @property
    def user(self):
        return self.authorization.user


class RecentActivity(models.Model):
    ADD = "ADD"
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    INTEGRATE = "INTEGRATE"
    TRAIN = "TRAIN"

    ACTIONS_CHOICES = {
        (ADD, "Add"),
        (CREATE, "Entity Created"),
        (UPDATE, "Entity updated"),
        (INTEGRATE, "Entity integrated"),
        (TRAIN, "Entity Trained"),
    }

    USER = "USER"
    FLOW = "FLOW"
    CHANNEL = "CHANNEL"
    TRIGGER = "TRIGGER"
    CAMPAIGN = "CAMPAIGN"
    AI = "AI"
    ENTITY_CHOICES = (
        (USER, "User Entity"),
        (FLOW, "Flow Entity"),
        (CHANNEL, "Channel Entity"),
        (TRIGGER, "Trigger Entity"),
        (CAMPAIGN, "Campaign Entity"),
        (AI, "Artificial Intelligence Entity"),
    )

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="project_recent_activity"
    )
    action = models.CharField(max_length=15, choices=ACTIONS_CHOICES)
    entity = models.CharField(max_length=20, choices=ENTITY_CHOICES)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="user_recent_activy"
    )
    entity_name = models.CharField(max_length=255, null=True)
    created_on = models.DateTimeField(_("created on"), auto_now_add=True)

    @property
    def action_description_key(self) -> str:
        actions = dict(
            ADD=dict(USER="joined-project"),
            CREATE=dict(
                TRIGGER="created-trigger",
                CAMPAIGN="created-campaign",
                FLOW="created-flow",
                CHANNEL="created-channel",
                AI="created-ai",
            ),
            UPDATE=dict(
                TRIGGER="edited-trigger",
                CAMPAIGN="edited-campaign",
                FLOW="edited-flow",
                CHANNEL="edited-channel",
            ),
            INTEGRATE=dict(AI="integrated-ai"),
            TRAIN=dict(AI="trained-ai"),
        )
        return actions[self.action][self.entity]

    @property
    def user_name(self):
        # TODO: move to User model
        if self.user.first_name and self.user.last_name:
            return f"{self.user.first_name} {self.user.last_name}"

        return self.user.email

    @property
    def to_json(self):
        data = {
            "user": self.user_name,
            "created_at": self.created_on,
            "action": self.action_description_key,
        }
        if self.entity_name:
            data.update({"name": self.entity_name})

        return data


class NewsletterOrganization(models.Model):
    title = models.CharField(_("title"), max_length=50)
    description = models.TextField(_("description"))
    organization = models.ForeignKey(
        Organization, models.CASCADE, related_name="org_newsletter"
    )
    newsletter = models.ForeignKey(
        Newsletter, models.CASCADE
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    def __str__(self):
        return f"Newsletter PK: {self.newsletter.pk} - {self.organization} - {self.title}"

    @property
    def organization_name(self):
        return self.organization.name

    def trial_end_date(self):
        return self.organization.organization_billing.trial_end_date

    @staticmethod
    def destroy_newsletter(organization: Organization):
        organization_newsletters = NewsletterOrganization.objects.filter(
            organization=organization
        )
        for newsletter in organization_newsletters:
            if isinstance(newsletter, NewsletterOrganization):
                newsletter.delete()
