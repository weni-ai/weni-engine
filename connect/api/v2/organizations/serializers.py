import logging
import re

from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError

from connect.common.models import (
    Organization,
    BillingPlan,
    OrganizationRole,
    RequestPermissionOrganization,
    OrganizationLevelRole,
    OrganizationAuthorization,
)
from connect.api.v1.organization.serializers import (
    BillingPlanSerializer,
    OrganizationAuthorizationSerializer,
)
from connect.api.v1.project.validators import CanContributeInOrganizationValidator
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
        user = self.context["request"].user

        authorizations = self.context["request"].data.get("organization").get("authorizations")

        if settings.CREATE_AI_ORGANIZATION:
            created, data = instance.create_ai_organization(user.email)
            if not created:
                return data

        self.create_authorizations(instance, authorizations, user)

        return instance

    def get_authorization(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None

        data = OrganizationAuthorizationSerializer(
            obj.get_user_authorization(request.user)
        ).data
        return data

    def create_authorizations(self, instance: Organization, authorizations: list, user: User):
        # Create authorization for the organization owner
        instance.authorizations.create(
            user=user, role=OrganizationRole.ADMIN.value
        )

        instance.send_email_organization_create()

        # Other users
        for authorization in authorizations:
            RequestPermissionOrganization.objects.create(
                email=authorization.get("user_email"),
                organization=instance,
                role=authorization.get("role"),
                created_by=user
            )


class PendingAuthorizationOrganizationSerializer(serializers.ModelSerializer):
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
        self.validate_email(attrs["email"])
        self.validate_role(attrs["role"])
        return attrs

    def validate_email(self, email):
        if ' ' in email:
            raise ValidationError(_("Email field cannot have spaces"))
        if bool(re.match('[A-Z]', email)):
            raise ValidationError(_("Email field cannot have uppercase characters"))

    def validate_role(self, role):
        if role == OrganizationLevelRole.NOTHING.value:
            raise PermissionDenied(_("You cannot set user role 0"))

    def get_user_data(self, obj):
        user = User.objects.filter(email=obj.email).first()
        return self.calculate_user_data(user)

    def calculate_user_data(self, user):
        if user:
            return {
                "name": f"{user.first_name} {user.last_name}",
                "photo": user.photo_url
            }
        return {
            "name": None,
            "photo": None
        }


class OrganizationExistingAuthorizationSerializer(serializers.ModelSerializer):
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


class NestedAuthorizationOrganizationSerializer(serializers.Serializer):
    pending_permissions = PendingAuthorizationOrganizationSerializer(many=True)
    existing_permissions = OrganizationExistingAuthorizationSerializer(many=True)

    def to_representation(self, instance):
        existing_permissions = instance.authorizations.all()
        pending_permissions = instance.requestpermissionorganization_set.all()

        pending_serializer = PendingAuthorizationOrganizationSerializer(
            pending_permissions, many=True
        )
        existing_serializer = OrganizationAuthorizationSerializer(
            existing_permissions, many=True
        )

        return {
            "pending_permissions": pending_serializer.data,
            "existing_permissions": existing_serializer.data,
        }
