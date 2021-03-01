from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from weni.api.v1.account.serializers import UserSerializer
from weni.common.models import Organization, OrganizationAuthorization


class OrganizationSeralizer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = [
            "uuid",
            "name",
            "description",
            "owner",
            "inteligence_organization",
            "authorizations",
        ]
        ref_name = None

    uuid = serializers.UUIDField(style={"show": False}, read_only=True)
    name = serializers.CharField(max_length=40, required=True)
    owner = UserSerializer(many=False, read_only=True)
    inteligence_organization = serializers.IntegerField(read_only=True)
    authorizations = serializers.SerializerMethodField(style={"show": False})

    def create(self, validated_data):
        import random

        validated_data.update({"owner": self.context["request"].user})
        validated_data.update({"inteligence_organization": random.randint(0, 1000000)})

        instance = super().create(validated_data)

        instance.authorizations.create(
            user=self.context["request"].user, role=OrganizationAuthorization.ROLE_ADMIN
        )

        return instance

    def get_authorizations(self, obj):
        auths = obj.authorizations.exclude(
            role=OrganizationAuthorization.ROLE_NOT_SETTED
        )
        return {
            "count": auths.count(),
            "users": [
                {"nickname": i.user.username, "name": i.user.first_name} for i in auths
            ],
        }


class OrganizationAuthorizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationAuthorization
        fields = [
            "uuid",
            "user",
            "user__username",
            "organization",
            "role",
            "level",
            "can_read",
            "can_contribute",
            "can_write",
            "is_admin",
            "created_at",
        ]
        read_only = ["user", "user__username", "organization", "role", "created_at"]
        ref_name = None

    user__username = serializers.SlugRelatedField(
        source="user", slug_field="username", read_only=True
    )


class OrganizationAuthorizationRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationAuthorization
        fields = ["role"]
        ref_name = None

    def validate(self, data):
        if self.instance.user == self.instance.organization.owner:
            raise PermissionDenied(_("The owner role can't be changed."))
        if data.get("role") == OrganizationAuthorization.LEVEL_NOTHING:
            raise PermissionDenied(_("You cannot set user role 0"))
        return data
