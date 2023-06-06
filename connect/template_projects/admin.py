from django.contrib import admin
from connect.template_projects.models import TemplateType, TemplateFeature, TemplateFlow


class TemplateFeatureInline(admin.TabularInline):
    model = TemplateFeature.template_type.through
    extra = 1


class TemplateFlowInline(admin.TabularInline):
    model = TemplateFlow
    extra = 1


class TemplateTypeAdmin(admin.ModelAdmin):
    inlines = [TemplateFeatureInline, TemplateFlowInline]
    search_fields = ["category", "level"]
    list_display = ["name", "category"]


class TemplateFeatureAdmin(admin.ModelAdmin):
    fields = ("name", "description", "type", "feature_identifier")


admin.site.register(TemplateType, TemplateTypeAdmin)
admin.site.register(TemplateFeature, TemplateFeatureAdmin)
