from django.db import models


class TemplateType(models.Model):

    category = models.CharField(max_length=255)
    description = models.TextField()
    name = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.description}, {self.category}, {self.name}"


class TemplateAI(models.Model):

    name = models.CharField(max_length=255)
    description = models.TextField()
    template_type = models.ForeignKey(TemplateType, on_delete=models.CASCADE, related_name='template_ais')

    def __str__(self):
        return f"{self.name} , {self.description}, {self.template_type}"


class TemplateFeatures(models.Model):

    features_types = [
        ("Flows", "Flows"),
        ("Integrations", "Integrations"),
        ("Intelligences", "Intelligences")
    ]

    description = models.TextField()
    name = models.CharField(max_length=255)  # description="Name of the AI, only available if type == 'Intelligences'"
    type = models.CharField(max_length=255, choices=features_types)
    feature_identifier = models.CharField(max_length=255)  # description="Identifier of the feature"

    def __str__(self):
        return f"{self.name}, {self.description}, {self.type}"
