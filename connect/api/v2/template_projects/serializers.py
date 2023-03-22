from rest_framework.serializers import ModelSerializer
from connect.template_projects.models import TemplateType, TemplateAI, TemplateFeatures


class TemplateTypeSerializer(ModelSerializer):
    class Meta:
        model = TemplateType
        fields = ['category', 'description', 'name']


class TemplateAISerializer(ModelSerializer):
    class Meta:
        model = TemplateAI
        fields = ['name', 'description', 'template_type']


class TemplateFeaturesSerializer(ModelSerializer):
    class Meta:
        model = TemplateFeatures
        fields = ['name', 'description', 'type', 'feature_identifier']
