from rest_framework import serializers

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
        ]
        ref_name = None

    uuid = serializers.UUIDField(style={"show": False}, read_only=True)
    name = serializers.CharField(max_length=40, required=True)
    owner = UserSerializer(many=False, read_only=True)
    inteligence_organization = serializers.IntegerField(read_only=True)

    def create(self, validated_data):
        import random

        validated_data.update({"owner": self.context["request"].user})
        validated_data.update({"inteligence_organization": random.randint(0, 1000000)})

        instance = super().create(validated_data)

        instance.authorizations.create(
            user=self.context["request"].user, role=OrganizationAuthorization.ROLE_ADMIN
        )

        return instance
