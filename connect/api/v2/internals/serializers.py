import logging
from django.contrib.auth import get_user_model
from django.utils.translation import ugettext_lazy as _

from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from connect.api.v1.project.validators import CanContributeInOrganizationValidator
from connect.common.models import (
    Organization,
    OrganizationAuthorization,
    RequestPermissionOrganization,
    OrganizationLevelRole,
    OrganizationRole,
    Project,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class InternalProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = [
            "uuid",
            "name",
            "flow_id"
        ]

    uuid = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)


class CustomParameterSerializer(serializers.Serializer):
    project_uuid = serializers.UUIDField(help_text="querystring parameter")


class OrganizationAISerializer(serializers.HyperlinkedModelSerializer):
    exclude_roles = [
        OrganizationRole.NOT_SETTED.value,
        OrganizationRole.VIEWER.value,
        OrganizationRole.SUPPORT.value,
    ]

    class Meta:
        model = Organization
        fields = [
            "uuid",
            "name",
            "authorizations",
            "owner",
        ]
        ref_name = None

    uuid = serializers.UUIDField(style={"show": False}, read_only=True)
    name = serializers.CharField(max_length=40, required=True)
    authorizations = serializers.SerializerMethodField(style={"show": False})
    owner = serializers.SerializerMethodField(style={"show": False})

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
                }
                for i in obj.authorizations.exclude(role__in=exclude_roles)
            ],
        }

    def get_owner(self, obj):
        user = (
            obj.authorizations.exclude(role__in=self.exclude_roles)
            .order_by("created_at")
            .first()
        )
        data = OrganizationAuthorizationSerializer(user).data

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
        return attrs

    def get_user_data(self, obj):
        user = User.objects.filter(email=obj.email)
        user_data = dict(name=f"{obj.email}", photo=None)
        if user.exists():
            user = user.first()
            user_data = dict(
                name=f"{user.first_name} {user.last_name}", photo=user.photo_url
            )

        return user_data
