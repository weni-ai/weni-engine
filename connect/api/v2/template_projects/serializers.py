from rest_framework.serializers import ModelSerializer
from connect.template_projects.models import TemplateType, TemplateFeature, TemplateSuggestion


class TemplateFeatureSerializer(ModelSerializer):

    class Meta:
        model = TemplateFeature
        fields = "__all__"


class TemplateTypeSerializer(ModelSerializer):

    template_features = TemplateFeatureSerializer(many=True)

    class Meta:
        model = TemplateType
        fields = [
            'uuid', 'category', 'description', 'name',
            'level', 'setup', 'photo', 'template_features',
            'photo_description', 'base_project_uuid'
        ]
        read_only_fields = ['uuid', 'template_features']


class RetrieveTemplateSerializer(ModelSerializer):

    class Meta:
        model = TemplateType
        fields = ['uuid', 'description', 'name']


class TemplateSuggestionSerializer(ModelSerializer):

    class Meta:
        model = TemplateSuggestion
        fields = ['suggestion', 'created_at', 'status']
