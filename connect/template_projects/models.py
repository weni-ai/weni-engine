import uuid as uuid4

from django.db import models
from django.contrib.postgres.fields import ArrayField
from .storage import TemplateTypeImageStorage


class TemplateType(models.Model):

    level_field = [("low", 1), ("medium", 2), ("high", 3)]
    uuid = models.UUIDField(
        "UUID", default=uuid4.uuid4
    )
    base_project_uuid = models.UUIDField(
        "base project", blank=True, null=True
    )
    category = ArrayField(base_field=models.CharField(max_length=255), default=list)
    description = models.TextField(blank=True, null=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    level = models.CharField(max_length=255, choices=level_field)
    setup = models.JSONField(blank=True, null=True)

    photo = models.ImageField(storage=TemplateTypeImageStorage(), blank=True, null=True)
    photo_description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name if self.name else str(self.uuid)

    def get_template_code(self, template_name):
        mapping_template = {
            "Suporte": "support",
            "Financeiro Integrado com a Omie | ChatGPT": "omie_financial+chatgpt",
            "Captura de Leads | ChatGPT": "lead_capture+chatgpt",
            "Captura de Leads": "lead_capture",
            "SAC | ChatGPT": "sac+chatgpt",
            "Financeiro Integrado com a Omie": "omie_financial",
            "Captura de leads com Omie": "omie_lead_capture",
        }
        return mapping_template.get(template_name, "blank")


class TemplateFeature(models.Model):

    features_types = [
        ("Flows", "Flows"),
        ("Integrations", "Integrations"),
        ("Intelligences", "Intelligences")
    ]

    description = models.TextField()
    name = models.CharField(max_length=255)  # description="Name of the AI, only available if type == 'Intelligences'"
    type = models.CharField(max_length=255, choices=features_types)
    feature_identifier = models.CharField(max_length=255)  # description="Identifier of the feature"
    template_type = models.ForeignKey(TemplateType, on_delete=models.CASCADE, related_name='template_features')

    def __str__(self):
        return self.name


class TemplateSuggestion(models.Model):

    suggestion = models.TextField()
    suggestion_type = [
        ("feature", "feature"),
        ("template", "template"),
        ("flow", "flow"),
        ("integration", "integration"),
        ("intelligence", "intelligence")
    ]
    type = models.CharField(max_length=255, choices=suggestion_type, default="template")
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=255, default="pending")

    def __str__(self):
        return f"{self.status}"
