from django.db import models
from .storage import TemplateTypeImageStorage, TemplateFlowFileStorage


class TemplateType(models.Model):

    level_field = [("low", 1), ("medium", 2), ("high", 3)]

    category = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    level = models.CharField(max_length=255, choices=level_field)
    setup = models.JSONField(blank=True, null=True)

    photo = models.ImageField(storage=TemplateTypeImageStorage(), blank=True, null=True)

    def __str__(self):
        return f"{self.id}"


class TemplateAI(models.Model):

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    template_type = models.ForeignKey(TemplateType, on_delete=models.CASCADE, related_name='template_ais')

    def __str__(self):
        return f"{self.id}"


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
    template_type = models.ManyToManyField(TemplateType, on_delete=models.CASCADE, related_name='template_features')

    def __str__(self):
        return f"{self.id}"


class TemplateFlow(models.Model):

    name = models.CharField(max_length=255)
    flow_url = models.FileField(storage=TemplateFlowFileStorage())
    template_type = models.ForeignKey(TemplateType, on_delete=models.CASCADE, related_name='template_flows')

    def __str__(self):
        return f"{self.id}"
