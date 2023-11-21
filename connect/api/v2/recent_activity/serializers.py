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


class ListRecentActivitySerializer(serializers.ModelSerializer):

    class Meta:
        model = RecentActivity
        fields = ['user', 'action', 'created_at', 'name']

    created_at = serializers.SerializerMethodField()
    action = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()

    def get_action(self, instance):
        return instance.action_description_key

    def get_created_at(self, instance):
        return instance.created_on

    def get_name(self, instance):
        return instance.entity_name

    def get_user(self, instance):
        return instance.user_name
