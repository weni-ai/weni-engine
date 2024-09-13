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
        if obj.translations.filter(language=lang).exists():
            translation = obj.translations.get(language=lang)
            return translation.description
        return None

    def get_name(self, obj):
        lang = self._get_language()
        if obj.translations.filter(language=lang).exists():
            translation = obj.translations.get(language=lang)
            return translation.name
        return None


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
        if obj.translations.filter(language=lang).exists():
            translation = obj.translations.get(language=lang)
            return translation.name
        return None

    def get_description(self, obj):
        lang = self._get_language()
        if obj.translations.filter(language=lang).exists():
            translation = obj.translations.get(language=lang)
            return translation.description
        return None

    def get_setup(self, obj):
        lang = self._get_language()
        if obj.translations.filter(language=lang).exists():
            translation = obj.translations.get(language=lang)
            return translation.setup
        return None

    def get_photo(self, obj):
        lang = self._get_language()
        if obj.translations.filter(language=lang).exists():
            translation = obj.translations.get(language=lang)
            return translation.photo.url
        return None

    def get_photo_description(self, obj):
        lang = self._get_language()
        if obj.translations.filter(language=lang).exists():
            translation = obj.translations.get(language=lang)
            return translation.photo_description
        return None

    def get_category(self, obj):
        lang = self._get_language()
        if obj.translations.filter(language=lang).exists():
            translation = obj.translations.get(language=lang)
            return translation.category
        return None

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
        translation = obj.translations.get(language=lang)
        return translation.description if translation else None

    def get_name(self, obj):
        lang = self._get_language()
        translation = obj.translations.get(language=lang)
        return translation.name if translation else None


class TemplateSuggestionSerializer(ModelSerializer):
    class Meta:
        model = TemplateSuggestion
        fields = ["suggestion", "created_at", "status"]
