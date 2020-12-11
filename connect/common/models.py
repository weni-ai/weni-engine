from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import ugettext_lazy as _


class DashboardNewsletter(models.Model):
    class Meta:
        verbose_name = _("dashboard newsletter")

    title = models.CharField(_("title"), max_length=36)
    description = models.TextField(_("description"))
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)


class ServicesStatus(models.Model):
    class Meta:
        verbose_name = _("service status")

    url = models.URLField(_("service url"))
    user = models.ForeignKey(User, models.CASCADE)
    status = models.BooleanField(_("status service"), default=False)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
