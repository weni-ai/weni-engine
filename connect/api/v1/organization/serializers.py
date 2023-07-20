import re
import logging

from django.http import JsonResponse
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework import status

from connect.api.v1.fields import TextField
from connect.api.v1.project.validators import CanContributeInOrganizationValidator
from connect.common.models import (
    Organization,
    OrganizationAuthorization,
    RequestPermissionOrganization,
    BillingPlan,
    OrganizationLevelRole,
    OrganizationRole
)
from connect.api.v1.internal.intelligence.intelligence_rest_client import IntelligenceRESTClient

User = get_user_model()
logger = logging.getLogger(__name__)


class BillingPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingPlan
        fields = [
            "id",
            "cycle",
            "payment_method",
            "next_due_date",
            "termination_date",
            "fixed_discount",
            "payment_method",
            "plan",
            "is_active",
            "final_card_number",
            "card_expiration_date",
            "cardholder_name",
            "card_brand",
            "payment_warnings",
            "problem_capture_invoice",
            "currenty_invoice",
            "contract_on",
            "trial_end_date",
            "days_till_trial_end"
        ]
        ref_name = None

    id = serializers.PrimaryKeyRelatedField(read_only=True, source="pk")
    cycle = serializers.ChoiceField(
        BillingPlan.BILLING_CHOICES,
        label=_("billing cycle"),
        default=BillingPlan._meta.get_field("cycle").default,
        read_only=True,
    )
    payment_method = serializers.ChoiceField(
        BillingPlan.PAYMENT_METHOD_CHOICES, label=_("payment method"), read_only=True
    )
    fixed_discount = serializers.FloatField(read_only=True)
    termination_date = serializers.DateField(read_only=True)
    next_due_date = serializers.DateField(read_only=True)
    plan = serializers.ChoiceField(
        BillingPlan.PLAN_CHOICES, label=_("plan"), default=BillingPlan.PLAN_FREE
    )
    is_active = serializers.BooleanField()
    contract_on = serializers.DateField()
    final_card_number = serializers.CharField(
        read_only=True,
        allow_null=True,
        allow_blank=True,
    )
    card_expiration_date = serializers.CharField(
        read_only=True,
        allow_null=True,
        allow_blank=True,
    )
    cardholder_name = TextField(
        read_only=True,
        allow_null=True,
        allow_blank=True,
    )
    card_brand = serializers.CharField(
        read_only=True,
        allow_null=True,
        allow_blank=True,
    )
    payment_warnings = serializers.ListField()
    problem_capture_invoice = serializers.BooleanField()
    currenty_invoice = serializers.DictField(
        read_only=True,
        help_text=_("Total active contacts and current invoice amount before closing"),
    )
    trial_end_date = serializers.DateTimeField(read_only=True)


class OrganizationSeralizer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Organization
        fields = [
            "uuid",
            "name",
            "description",
            "organization_billing",
            "organization_billing_plan",
            "inteligence_organization",
            "authorizations",
            "authorization",
            "created_at",
            "is_suspended",
            "extra_integration",
            "enforce_2fa"
        ]
        ref_name = None

    uuid = serializers.UUIDField(style={"show": False}, read_only=True)
    name = serializers.CharField(max_length=40, required=True)
    inteligence_organization = serializers.IntegerField(read_only=True)
    authorizations = serializers.SerializerMethodField(style={"show": False})
    authorization = serializers.SerializerMethodField(style={"show": False})
    organization_billing = BillingPlanSerializer(read_only=True)
    organization_billing_plan = serializers.ChoiceField(
        BillingPlan.PLAN_CHOICES,
        label=_("plan"),
        source="organization_billing__plan",
        write_only=True,
        required=True,
    )
    is_suspended = serializers.BooleanField(
        label=_("is suspended"),
        default=False,
        required=False,
        help_text=_("Whether this organization is currently suspended."),
    )
    extra_integration = serializers.IntegerField(read_only=True)
    enforce_2fa = serializers.BooleanField(
        label=_("enforce 2fa"),
        required=False,
        help_text=_("if this field is true, only users with 2fa activated can access the org")
    )

    def create_organization(self, validated_data): # pragma: no cover
        organization = {"id": 0}
        if not settings.TESTING:
            ai_client = IntelligenceRESTClient()
            organization = ai_client.create_organization(
                user_email=self.context["request"].user.email,
                organization_name=validated_data.get("name")
            )

        validated_data.update({"inteligence_organization": organization.get("id")})

        # Added for the manager to set the date when the next invoice will be generated
        validated_data.update(
            {
                "organization_billing__cycle": BillingPlan._meta.get_field(
                    "cycle"
                ).default
            }
        )

        instance = super(OrganizationSeralizer, self).create(validated_data)

        instance.authorizations.create(
            user=self.context["request"].user, role=OrganizationRole.ADMIN.value
        )

        return instance

    def create(self, validated_data): # pragma: no cover
        data = {}
        try:
            ai_client = IntelligenceRESTClient()
            Organization = ai_client.create_organization(
                user_email=self.context["request"].user.email,
                organization_name=validated_data.get("name"),
            )
        except Exception as error:
            data.update(
                {
                    "message": "Could not create organization in AI module",
                    "status": "FAILED",
                }
            )
            logger.error(error)
            return JsonResponse(data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Billing Cycle
        # Added for the manager to set the date when new invoice will be generated
        billing_cycle = BillingPlan._meta.get_field("cycle").default

        validated_data.update(
            {
                "inteligence_organization": Organization.get("id"),
                "organization_billing__cycle": billing_cycle,
            }
        )
        # create organization object
        instance = super(OrganizationSeralizer, self).create(validated_data)

        # Create authorization for the organization owner
        instance.authorizations.create(
            user=self.context["request"].user, role=OrganizationRole.ADMIN.value
        )
        return instance

    def get_authorizations(self, obj):
        exclude_roles = [OrganizationRole.NOT_SETTED.value, OrganizationRole.VIEWER.value, OrganizationRole.SUPPORT.value]
        return {
            "count": obj.authorizations.count(),
            "users": [
                {
                    "username": i.user.username,
                    "first_name": i.user.first_name,
                    "last_name": i.user.last_name,
                    "role": i.role,
                    "photo_user": i.user.photo_url,
                }
                for i in obj.authorizations.exclude(role__in=exclude_roles)
            ],
        }

    def get_authorization(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None

        data = OrganizationAuthorizationSerializer(
            obj.get_user_authorization(request.user)
        ).data
        return data


class OrganizationAuthorizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationAuthorization
        fields = [
            "uuid",
            "user",
            "user__id",
            "user__username",
            "user__email",
            "user__photo",
            "organization",
            "role",
            "can_read",
            "can_contribute",
            "can_contribute_billing",
            "can_write",
            "is_admin",
            "is_financial",
            "created_at",
        ]
        read_only = ["user", "user__username", "organization", "role", "created_at"]
        ref_name = None

    user__id = serializers.IntegerField(source="user.id", read_only=True)
    user__username = serializers.SlugRelatedField(
        source="user", slug_field="username", read_only=True
    )
    user__email = serializers.EmailField(
        source="user.email", label=_("Email"), read_only=True
    )
    user__photo = serializers.ImageField(
        source="user.photo", label=_("User photo"), read_only=True
    )


class OrganizationAuthorizationRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationAuthorization
        fields = ["role"]
        ref_name = None

    def validate(self, attrs):
        if attrs.get("role") == OrganizationLevelRole.NOTHING.value:
            raise PermissionDenied(_("You cannot set user role 0"))
        return attrs


class RequestPermissionOrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestPermissionOrganization
        fields = ["id", "email", "organization", "role", "created_by", "user_data"]
        ref_name = None

    email = serializers.EmailField(max_length=254, required=True)
    organization = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects,
        style={"show": False},
        required=True,
        validators=[CanContributeInOrganizationValidator()],
    )
    created_by = serializers.HiddenField(
        default=serializers.CurrentUserDefault(), style={"show": False}
    )
    user_data = serializers.SerializerMethodField()

    def validate(self, attrs):
        if attrs.get("role") == OrganizationLevelRole.NOTHING.value:
            raise PermissionDenied(_("You cannot set user role 0"))

        email = attrs.get("email")

        if ' ' in email:
            raise ValidationError(
                _("Email field cannot have spaces")
            )

        if bool(re.match('[A-Z]', email)):
            raise ValidationError(
                _("Email field cannot have uppercase characters")
            )

        return attrs

    def get_user_data(self, obj):
        user = User.objects.filter(email=obj.email)
        user_data = dict(
            name=f"{obj.email}",
            photo=None
        )
        if user.exists():
            user = user.first()
            user_data = dict(
                name=f"{user.first_name} {user.last_name}",
                photo=user.photo_url
            )

        return user_data
