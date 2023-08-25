from rest_framework.serializers import ModelSerializer
from connect.template_projects.models import TemplateType, TemplateAI, TemplateFeature
from rest_framework import serializers


class TemplateAISerializer(ModelSerializer):

    class Meta:

        model = TemplateAI
        fields = "__all__"


class TemplateFeatureSerializer(ModelSerializer):

    class Meta:
        model = TemplateFeature
        fields = "__all__"


class TemplateTypeSerializer(ModelSerializer):

    features = serializers.SerializerMethodField()
    ais = serializers.SerializerMethodField()

    class Meta:
        model = TemplateType
        fields = [
            'id', 'category', 'description', 'name',
            'level', 'setup', 'photo', 'features',
            'ais', 'photo_description', 'uuid'
        ]

    def get_features(self, obj):
        return TemplateFeatureSerializer(obj.template_features.all(), many=True).data

    def get_ais(self, obj):
        return TemplateAISerializer(obj.template_ais.all(), many=True).data


class RetrieveTemplateSerializer(ModelSerializer):

    class Meta:
        model = TemplateType
        fields = ['id', 'description', 'name', 'uuid']
