from django.contrib import admin
from connect.template_projects.models import TemplateType, TemplateFeature, TemplateFlow

# Register your models here.
admin.site.register(TemplateType)
admin.site.register(TemplateFeature)
admin.site.register(TemplateFlow)
