from rest_framework import serializers

from connect.common.models import Project, RecentActivity
from connect.authentication.models import User


class RecentActivitySerializer(serializers.ModelSerializer):

    class Meta:
        model = RecentActivity
        fields = ['user', 'action', 'entity', 'entity_name', 'intelligence_id', 'flow_organization', 'project_uuid', 'project']

    user = serializers.SlugRelatedField(slug_field='email', queryset=User.objects.all(), required=False)
    project = serializers.SlugRelatedField(slug_field='uuid', queryset=Project.objects.all(), required=False)
    action = serializers.CharField(required=False)
    entity = serializers.CharField(required=False)
    entity_name = serializers.CharField(required=False)
    intelligence_id = serializers.CharField(required=False)
    flow_organization = serializers.CharField(required=False)
    project_uuid = serializers.CharField(required=False)

    def create(self, validated_data):
        user = validated_data.get('user')
        return RecentActivity.create_recent_activities(validated_data, user)
