from django.db import models
from django.utils.translation import ugettext_lazy as _


class DashboardNewsletter(models.Model):
    class Meta:
        verbose_name = _("dashboard newsletter")

    title = models.CharField(_("title"), max_length=36)
    description = models.TextField(_("description"))
