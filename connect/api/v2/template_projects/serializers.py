from rest_framework.serializers import ModelSerializer
from connect.template_projects.models import TemplateType, TemplateFeature, TemplateFlow
from rest_framework import serializers


class TemplateFeatureSerializer(ModelSerializer):

    class Meta:
        model = TemplateFeature
        fields = "__all__"


class TemplateTypeSerializer(ModelSerializer):

    features = serializers.SerializerMethodField()
    flows = serializers.SerializerMethodField()

    class Meta:
        model = TemplateType
        fields = ['id', 'category', 'description', 'name', 'level', 'setup', 'photo', 'features', 'flows']

    def get_features(self, obj):
        return TemplateFeatureSerializer(obj.template_features.all(), many=True).data

    def get_flows(self, obj):

        return NestedTemplateFlowSerializer(obj.template_flows.all(), many=True).data


class RetrieveTemplateSerializer(ModelSerializer):

    class Meta:
        model = TemplateType
        fields = ['id', 'description', 'name']


class TemplateFlowSerializer(ModelSerializer):

    class Meta:
        model = TemplateFlow
        exclude = ['template_type']
        fields = "__all__"


class NestedTemplateFlowSerializer(ModelSerializer):

    class Meta:
        model = TemplateFlow
        exclude = ['template_type']
