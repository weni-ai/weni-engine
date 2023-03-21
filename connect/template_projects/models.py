from django.db import models


class TemplateType(models.Model):

    category = models.CharField(max_length=255)
    description = models.TextField()
    name = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.description}, {self.category}, {self.name}"


class TemplateIA(models.Model):

    name = models.CharField(max_length=255)
    description = models.TextField()
    template_type = models.ForeignKey(TemplateType, on_delete=models.CASCADE, related_name='template_ais')

    def __str__(self):
        return f"{self.name} , {self.description}, {self.template_type}"
