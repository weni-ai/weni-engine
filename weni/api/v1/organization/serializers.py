from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from weni.common.models import Organization


class OrganizationSeralizer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = [
            "uuid",
            "name",
            "description",
        ]
        ref_name = None

    read_only = ["id", "verificated"]

    uuid = serializers.UUIDField(style={"show": False}, read_only=True)
    name = serializers.CharField(max_length=40, required=True)
