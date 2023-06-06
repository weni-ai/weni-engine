from django.contrib import admin
from connect.template_projects.models import TemplateType, TemplateFeature, TemplateAI, TemplateFlow

# Register your models here.
admin.site.register(TemplateType)
admin.site.register(TemplateFeature)
admin.site.register(TemplateAI)
admin.site.register(TemplateFlow)
