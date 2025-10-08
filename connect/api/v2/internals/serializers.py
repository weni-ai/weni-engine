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
            "flow_id",
            "flow_organization",
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


# CRM Serializers for the new CRM Organizations endpoint


class CRMUserSerializer(serializers.ModelSerializer):
    """Serializer for user data in CRM responses"""

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "role", "role_name"]

    role = serializers.SerializerMethodField()
    role_name = serializers.SerializerMethodField()

    def get_role(self, obj):
        """Get role from the authorization context"""
        authorization = getattr(obj, "_authorization", None)
        return authorization.role if authorization else None

    def get_role_name(self, obj):
        """Get human-readable role name"""
        authorization = getattr(obj, "_authorization", None)
        if authorization:
            if hasattr(authorization, "role_verbose"):
                return authorization.role_verbose
            # Fallback to choices lookup
            role_choices = dict(authorization.ROLE_CHOICES)
            return role_choices.get(authorization.role, "unknown")
        return None


class CRMProjectSerializer(serializers.ModelSerializer):
    """Serializer for project data in CRM responses"""

    class Meta:
        model = Project
        fields = ["name", "uuid", "vtex_account"]


class CRMOrganizationSerializer(serializers.ModelSerializer):
    """Main serializer for CRM Organization responses"""

    class Meta:
        model = Organization
        fields = ["uuid", "name", "created_at", "users", "projects"]

    users = serializers.SerializerMethodField()
    projects = serializers.SerializerMethodField()

    def get_users(self, obj):
        """Get organization users excluding NOT_SETTED roles"""
        org_authorizations = obj.authorizations.exclude(
            role=OrganizationRole.NOT_SETTED.value
        ).select_related("user")

        users = []
        for auth in org_authorizations:
            auth.user._authorization = auth
            users.append(auth.user)

        return CRMUserSerializer(users, many=True).data

    def get_projects(self, obj):
        """Get all organization projects"""
        projects = obj.project.all()
        return CRMProjectSerializer(projects, many=True).data
