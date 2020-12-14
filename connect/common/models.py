from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import ugettext_lazy as _


class DashboardNewsletter(models.Model):
    class Meta:
        verbose_name = _("dashboard newsletter")

    title = models.CharField(_("title"), max_length=36)
    description = models.TextField(_("description"))
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)


class Service(models.Model):
    class Meta:
        verbose_name = _("service")

    url = models.URLField(_("service url"), unique=True)
    status = models.BooleanField(_("status service"), default=False)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    default = models.BooleanField(_("service default"), default=False)


class ServiceStatus(models.Model):
    class Meta:
        verbose_name = _("service status")
        ordering = ["created_at"]

    service = models.OneToOneField(Service, models.CASCADE)
    user = models.ForeignKey(User, models.CASCADE)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
