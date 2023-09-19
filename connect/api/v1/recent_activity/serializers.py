import logging
from rest_framework import serializers
from connect.common.models import RecentActivity

logger = logging.getLogger(__name__)


class RecentActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = RecentActivity
        fields = ["user", "created_at", "action", "name"]

    user = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()

    def get_user(self, obj):
        return obj.user_name

    def get_name(self, obj):
        return obj.entity_name

    def get_created_at(self, obj):
        return obj.created_on
