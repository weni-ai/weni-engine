from django.contrib import admin
from connect.template_projects.models import (
    TemplateType,
    TemplateFeature,
    TemplateSuggestion,
    TemplateTypeTranslation,
    TemplateFeatureTranslation,
)

# Register your models here.
admin.site.register(TemplateSuggestion)


class TemplateTypeTranslationStackedInline(admin.StackedInline):
    model = TemplateTypeTranslation
    extra = 1


class TemplateFeatureTranslationStackedInline(admin.StackedInline):
    model = TemplateFeatureTranslation
    extra = 1


class TemplateTypeAdmin(admin.ModelAdmin):
    inlines = [TemplateTypeTranslationStackedInline]


class TemplateFeatureAdmin(admin.ModelAdmin):
    inlines = [TemplateFeatureTranslationStackedInline]


admin.site.register(TemplateType, TemplateTypeAdmin)
admin.site.register(TemplateFeature, TemplateFeatureAdmin)
