from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _

from weni.authentication.models import User


class Newsletter(models.Model):
    class Meta:
        verbose_name = _("dashboard newsletter")

    title = models.CharField(_("title"), max_length=36)
    description = models.TextField(_("description"))
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    def __str__(self):
        return self.title


class Service(models.Model):
    class Meta:
        verbose_name = _("service")

    url = models.URLField(_("service url"), unique=True)
    status = models.BooleanField(_("status service"), default=False)
    rocket_chat = models.BooleanField(_("is it a rocketchat server?"), default=False)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    last_updated = models.DateTimeField(_("last updated"), auto_now_add=True)
    default = models.BooleanField(_("service default"), default=False)

    def __str__(self):
        return self.url


class ServiceStatus(models.Model):
    class Meta:
        verbose_name = _("service status")
        ordering = ["created_at"]
        unique_together = ["service", "user"]

    service = models.ForeignKey(Service, models.CASCADE)
    user = models.ForeignKey(User, models.CASCADE, related_name="service_status")
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    def __str__(self):
        return self.service.url


@receiver(post_save, sender=User)
def create_service_status(sender, instance, created, **kwargs):
    if created:
        for service in Service.objects.filter(default=True):
            instance.service_status.create(service=service)


@receiver(post_save, sender=Service)
def create_service_default_in_all_user(sender, instance, created, **kwargs):
    if created and instance.default:
        for user in User.objects.all():
            user.service_status.create(service=instance)
