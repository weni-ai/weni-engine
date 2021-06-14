from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from weni.api.v1.project.validators import CanContributeInOrganizationValidator
from weni.common import tasks
from weni.common.models import (
    Organization,
    OrganizationAuthorization,
    RequestPermissionOrganization,
)


class OrganizationSeralizer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = [
            "uuid",
            "name",
            "description",
            "inteligence_organization",
            "authorizations",
            "authorization",
            "created_at",
        ]
        ref_name = None

    uuid = serializers.UUIDField(style={"show": False}, read_only=True)
    name = serializers.CharField(max_length=40, required=True)
    inteligence_organization = serializers.IntegerField(read_only=True)
    authorizations = serializers.SerializerMethodField(style={"show": False})
    authorization = serializers.SerializerMethodField(style={"show": False})

    def create(self, validated_data):
        task = tasks.create_organization.delay(  # pragma: no cover
            validated_data.get("name"),
            self.context["request"].user.email,
        )
        if not settings.TESTING:
            task.wait()  # pragma: no cover

        organization = task.result

        validated_data.update({"inteligence_organization": organization.get("id")})

        instance = super().create(validated_data)

        instance.send_email_organization_create(
            email=self.context["request"].user.email,
            first_name=self.context["request"].user.first_name,
        )

        instance.authorizations.create(
            user=self.context["request"].user, role=OrganizationAuthorization.ROLE_ADMIN
        )

        return instance

    def get_authorizations(self, obj):
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
                for i in obj.authorizations.all()
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
            "can_write",
            "is_admin",
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
        if attrs.get("role") == OrganizationAuthorization.LEVEL_NOTHING:
            raise PermissionDenied(_("You cannot set user role 0"))
        return attrs


class RequestPermissionOrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestPermissionOrganization
        fields = ["id", "email", "organization", "role", "created_by"]
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

    def validate(self, attrs):
        if attrs.get("role") == OrganizationAuthorization.LEVEL_NOTHING:
            raise PermissionDenied(_("You cannot set user role 0"))
        return attrs
