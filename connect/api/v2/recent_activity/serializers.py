from rest_framework import serializers

from connect.common.models import Project, RecentActivity
from connect.authentication.models import User


class RecentActivityListSerializer(serializers.ListSerializer):
    def to_representation(self, data):
        request = self.context.get('request')
        project_uuid = request.query_params.get("project")

        try:
            project = Project.objects.get(uuid=project_uuid)
        except Project.DoesNotExist:
            raise serializers.ValidationError({"message": "Project does not exist."})

        if not project.project_authorizations.filter(user__email=request.user.email).exists():
            raise serializers.ValidationError({"message": "Permission denied."})

        recent_activities = RecentActivity.objects.filter(project__uuid=project_uuid).order_by("-created_on")
        return super().to_representation(recent_activities)


class RecentActivitySerializer(serializers.ModelSerializer):

    class Meta:
        model = RecentActivity
        fields = ['user', 'action', 'entity', 'entity_name', 'intelligence_id', 'flow_organization', 'project_uuid', 'project']
        list_serializer_class = RecentActivityListSerializer

    user = serializers.SlugRelatedField(slug_field='email', queryset=User.objects.all())
    project = serializers.SlugRelatedField(slug_field='uuid', queryset=Project.objects.all())
    action = serializers.CharField()
    entity = serializers.CharField()
    entity_name = serializers.CharField(required=False)
    intelligence_id = serializers.CharField(required=False)
    flow_organization = serializers.CharField(required=False)
    project_uuid = serializers.CharField(required=False)

    def create(self, validated_data):
        user = validated_data.get('user')
        return RecentActivity.create_recent_activities(validated_data, user)
