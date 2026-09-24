from rest_framework import serializers

from connect.change_history.models import ChangeEvent


class ListProjectChangeHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ChangeEvent
        fields = [
            "uuid",
            "project_uuid",
            "user_email",
            "occurred_at",
            "action",
            "entity",
            "module",
            "object_id",
            "object_name",
            "user_ip",
        ]


class RetrieveProjectChangeHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ChangeEvent
        fields = [
            "uuid",
            "project_uuid",
            "user_email",
            "occurred_at",
            "action",
            "entity",
            "module",
            "object_id",
            "object_name",
            "old_value",
            "new_value",
            "user_ip",
        ]
