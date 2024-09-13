from rest_framework.serializers import ModelSerializer, SerializerMethodField

from connect.template_projects.models import (
    TemplateFeature,
    TemplateSuggestion,
    TemplateType,
)


class TemplateFeatureSerializer(ModelSerializer):
    description = SerializerMethodField()
    name = SerializerMethodField()

    class Meta:
        model = TemplateFeature
        fields = [
            "description",
            "name",
            "type",
            "feature_identifier",
            "template_type",
        ]

    def _get_language(self):
        request = self.context.get("request")
        return request.user.language

    def get_description(self, obj):
        lang = self._get_language()
        return obj.translations.get(language=lang).description

    def get_name(self, obj):
        lang = self._get_language()
        return obj.translations.get(language=lang).name


class TemplateTypeSerializer(ModelSerializer):

    name = SerializerMethodField()
    description = SerializerMethodField()
    setup = SerializerMethodField()
    photo = SerializerMethodField()
    photo_description = SerializerMethodField()
    category = SerializerMethodField()
    features = SerializerMethodField()

    class Meta:
        model = TemplateType
        fields = [
            "uuid",
            "category",
            "description",
            "name",
            "level",
            "setup",
            "photo",
            "features",
            "photo_description",
            "base_project_uuid",
        ]

    def _get_language(self):
        request = self.context.get("request")
        return request.user.language

    def get_name(self, obj):
        lang = self._get_language()
        return obj.translations.get(language=lang).name

    def get_description(self, obj):
        lang = self._get_language()
        return obj.translations.get(language=lang).description

    def get_setup(self, obj):
        lang = self._get_language()
        return obj.translations.get(language=lang).setup

    def get_photo(self, obj):
        lang = self._get_language()
        translation = obj.translations.get(language=lang)
        return translation.photo.url if translation.photo else None

    def get_photo_description(self, obj):
        lang = self._get_language()
        return obj.translations.get(language=lang).photo_description

    def get_category(self, obj):
        lang = self._get_language()
        return obj.translations.get(language=lang).category

    def get_features(self, obj):
        return TemplateFeatureSerializer(
            obj.template_features.all(), many=True, context=self.context
        ).data


class RetrieveTemplateSerializer(ModelSerializer):
    description = SerializerMethodField()
    name = SerializerMethodField()

    class Meta:
        model = TemplateType
        fields = ["uuid", "description", "name"]

    def _get_language(self):
        request = self.context.get("request")
        return request.user.language

    def get_description(self, obj):
        lang = self._get_language()
        return obj.translations.get(language=lang).description

    def get_name(self, obj):
        lang = self._get_language()
        return obj.translations.get(language=lang).name


class TemplateSuggestionSerializer(ModelSerializer):
    class Meta:
        model = TemplateSuggestion
        fields = ["suggestion", "created_at", "status"]
