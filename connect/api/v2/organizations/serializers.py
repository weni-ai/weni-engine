import logging
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from rest_framework import serializers

from connect.common.models import (
    Organization,
    BillingPlan,
    OrganizationRole,
)
from connect.api.v1.internal.intelligence.intelligence_rest_client import (
    IntelligenceRESTClient,
)
from connect.api.v1.organization.serializers import (
    BillingPlanSerializer,
    OrganizationAuthorizationSerializer,
)

User = get_user_model()
logger = logging.getLogger(__name__)


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
            "enforce_2fa",
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
        help_text=_(
            "if this field is true, only users with 2fa activated can access the org"
        ),
    )

    def create_organization(self, validated_data):
        organization = {"id": 0}
        if not settings.TESTING:
            ai_client = IntelligenceRESTClient()
            organization = ai_client.create_organization(
                user_email=self.context["request"].user.email,
                organization_name=validated_data.get("name"),
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

    def create(self, validated_data):
        # Billing Cycle
        # Added for the manager to set the date when new invoice will be generated
        billing_cycle = BillingPlan._meta.get_field("cycle").default

        validated_data.update(
            {
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
        exclude_roles = [
            OrganizationRole.NOT_SETTED.value,
            OrganizationRole.VIEWER.value,
            OrganizationRole.SUPPORT.value,
        ]
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
