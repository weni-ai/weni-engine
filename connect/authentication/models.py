import requests

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db.models import JSONField
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils import translation

from connect.common.utils import send_email
from connect.storages import AvatarUserMediaStorage

from connect.api.v1.keycloak import KeycloakControl


class UserManager(BaseUserManager):
    def _create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError("The given email must be set")
        if not username:
            raise ValueError("The given nick must be set")

        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("is_superuser", False)

        return self._create_user(email, username, password, **extra_fields)

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_staff", True)

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    first_name = models.CharField(_("first name"), max_length=30, blank=True)
    last_name = models.CharField(_("last name"), max_length=150, blank=True)
    email = models.EmailField(_("email"), unique=True, help_text=_("User's email."))

    username = models.CharField(
        _("username"),
        max_length=150,
        unique=True,
        help_text=_(
            "Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only."
        ),
        validators=[UnicodeUsernameValidator()],
        error_messages={
            "unique": _("A user with that username already exists."),
        },
    )

    photo = models.ImageField(
        _("photo user"), storage=AvatarUserMediaStorage(), null=True
    )

    language = models.CharField(
        verbose_name=_("Language"),
        max_length=64,
        choices=settings.LANGUAGES,
        default=settings.DEFAULT_LANGUAGE,
        help_text=_("The primary language used by this user"),
    )

    is_staff = models.BooleanField(_("staff status"), default=False)
    is_active = models.BooleanField(_("active"), default=True)

    joined_at = models.DateField(_("joined at"), auto_now_add=True)

    short_phone_prefix = models.IntegerField(
        verbose_name=_("Phone Prefix Country"),
        help_text=_("Phone prefix of the user"),
        null=True,
    )

    phone = models.BigIntegerField(
        verbose_name=_("Telephone Number"),
        help_text=_("Phone number of the user; include area code"),
        null=True,
    )

    last_update_profile = models.DateTimeField(
        verbose_name=_("Last Updated Profile"),
        null=True,
    )

    utm = JSONField(verbose_name=_("UTM Marketing"), default=dict)
    email_marketing = models.BooleanField(
        verbose_name=_("Allows receiving marketing emails"), default=True
    )
    has_2fa = models.BooleanField(_("Two factor authentication"), default=False)

    company_name = models.CharField(
        verbose_name=_("company name"),
        max_length=100,
        null=True,
        blank=True,
    )
    company_phone_number = models.BigIntegerField(
        verbose_name=_("company phone number"),
        help_text=_("company phone number"),
        null=True,
    )
    number_people = models.IntegerField(
        verbose_name=_("number of people"),
        help_text=_("number of people working in this company"),
        null=True,
        blank=True,
    )
    company_sector = models.CharField(
        verbose_name=_("company sector"),
        max_length=100,
        null=True,
        blank=True,
    )
    weni_helps = models.CharField(
        verbose_name=_("weni helps"),
        help_text=_("how the weni platform will help your team"),
        max_length=100,
        null=True,
        blank=True,
    )
    company_segment = models.CharField(
        verbose_name=_("company segment"),
        help_text=_("the segment of your company"),
        max_length=100,
        null=True,
        blank=True,
    )
    position = models.CharField(
        verbose_name=_("company position"),
        help_text=_("Your position in the company"),
        max_length=100,
        null=True,
        blank=True,
    )
    first_login = models.BooleanField(default=False)
    first_login_token = models.TextField(null=True)

    objects = UserManager()

    @property
    def token_generator(self):
        return PasswordResetTokenGenerator()

    @property
    def other_positions(self):
        return (
            self.position.split(":")[1]
            if self.position and "other:" in self.position
            else None
        )

    def check_password_reset_token(self, token):
        return self.token_generator.check_token(self, token)

    def send_change_password_email(self):
        if not settings.SEND_EMAILS:
            return False  # pragma: no cover
        context = {"name": self.first_name}

        with translation.override(self.language):
            send_email(
                _("Your password has been changed"),
                self.email,
                "authentication/emails/change_password.txt",
                "authentication/emails/change_password.html",
                context,
            )

    def send_email_access_password(self, password: str):
        if not settings.SEND_EMAILS:
            return False
        context = {
            "email": self.email,
            "name": self.first_name,
            "password": password,
        }
        with translation.override(self.language):
            send_email(
                _("Your Weni Platform account is ready! Log in now"),
                self.email,
                "authentication/emails/first_password.txt",
                "authentication/emails/first_password.html",
                context,
            )

    def send_request_flow_user_info(self, flow_data):  # pragma: no cover
        if not flow_data.get("send_request_flow"):
            return False
        company_size_mapping = [
            "1 - 20",
            "21 - 50",
            "51 - 300",
            "301 - 1000",
            "1001+",
            "somente eu",
            "2 - 10",
            "11 - 20",
        ]
        requests.post(
            url=f"{settings.FLOWS_URL}api/v2/flow_starts.json",
            json={
                "flow": flow_data.get("flow_uuid"),
                "params": {
                    "first_name": self.first_name,
                    "last_name": self.last_name,
                    "email": self.email,
                    "language": self.language,
                    "short_phone_prefix": self.short_phone_prefix,
                    "phone": self.phone,
                    "utm": self.utm,
                    "email_marketing": self.email_marketing,
                    "company_colaborators": (
                        company_size_mapping[self.number_people]
                        if self.number_people
                        else None
                    ),
                    "company_name": self.company_name,
                    "company_sector": self.company_sector,
                    "company_segment": self.company_segment,
                    "weni_helps": self.weni_helps,
                    "position": self.position,
                },
                "urns": [f"mailto:{self.email}"],
            },
            headers={"Authorization": f"Token {flow_data.get('token_authorization')}"},
        )

    @property
    def photo_url(self):
        if self.photo and hasattr(self.photo, "url"):
            return self.photo.url

    def update_language(self, language: str):
        from connect.api.v1.internal.chats.chats_rest_client import ChatsRESTClient
        from connect.api.v1.internal.flows.flows_rest_client import FlowsRESTClient
        from connect.api.v1.internal.intelligence.intelligence_rest_client import (
            IntelligenceRESTClient,
        )
        from connect.api.v1.internal.insights.insights_rest_client import (
            InsightsRESTClient,
        )

        chats_rest = ChatsRESTClient()
        flows_rest = FlowsRESTClient()
        intelligence_rest = IntelligenceRESTClient()
        insights_rest = InsightsRESTClient()
        self.language = language
        self.save(update_fields=["language"])

        chats_rest.update_user_language(self.email, self.language)
        flows_rest.update_language(self.email, self.language)
        intelligence_rest.update_language(self.email, self.language)
        insights_rest.update_user_language(self.email, self.language)

    def save_first_login_token(self, token: str):
        self.first_login_token = token
        self.save(update_fields=["first_login_token"])

    def set_verify_email(self):
        self.first_login = False
        keycloak = KeycloakControl()
        keycloak.set_verify_email(self.email)

        self.save(update_fields=["first_login"])

    def set_identity_providers(self, identity_provider: str) -> None:
        if not self.identity_provider.filter(provider=identity_provider).exists():
            self.identity_provider.create(provider=identity_provider)

    @property
    def get_company_data(self):
        return dict(
            company_name=self.company_name,
            company_segment=self.company_segment,
            company_sector=self.company_sector,
            number_people=self.number_people,
            weni_helps=self.weni_helps,
        )


class UserEmailSetup(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="email_setup"
    )
    receive_project_emails = models.BooleanField(default=True)
    receive_organization_emails = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"User: Receive Organization emails: {self.receive_organization_emails}, Receive Project emails: {self.receive_project_emails}"


class UserIdentityProvider(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="identity_provider"
    )
    provider = models.CharField(max_length=255)
