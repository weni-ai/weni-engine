from rest_framework.serializers import ModelSerializer
from connect.template_projects.models import TemplateType, TemplateFeature
from rest_framework import serializers


class TemplateFeatureSerializer(ModelSerializer):

    class Meta:
        model = TemplateFeature
        fields = "__all__"


class TemplateTypeSerializer(ModelSerializer):

    features = serializers.SerializerMethodField()

    class Meta:
        model = TemplateType
        fields = [
            'id', 'category', 'description', 'name',
            'level', 'setup', 'photo', 'features',
            'photo_description', 'uuid', 'base_project_uuid'
        ]

    def get_features(self, obj):
        return TemplateFeatureSerializer(obj.template_features.all(), many=True).data


class RetrieveTemplateSerializer(ModelSerializer):

    class Meta:
        model = TemplateType
        fields = ['id', 'description', 'name', 'uuid']
