import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from weni.authentication.models import User
from weni.common.models import (
    Project,
    Service,
    Organization,
    OrganizationAuthorization,
    RequestPermissionOrganization,
)
from weni.celery import app as celery_app

logger = logging.getLogger("weni.common.signals")


@receiver(post_save, sender=Project)
def create_service_status(sender, instance, created, **kwargs):
    if created:
        for service in Service.objects.filter(default=True):
            instance.service_status.create(service=service)


@receiver(post_save, sender=Service)
def create_service_default_in_all_user(sender, instance, created, **kwargs):
    if created and instance.default:
        for project in Project.objects.all():
            project.service_status.create(service=instance)


@receiver(post_save, sender=Organization)
def update_organization(sender, instance, **kwargs):
    celery_app.send_task(
        "update_organization",
        args=[instance.inteligence_organization, instance.name],
    )


@receiver(post_save, sender=OrganizationAuthorization)
def org_authorizations(sender, instance, **kwargs):
    celery_app.send_task(
        "update_user_permission_organization",
        args=[
            instance.organization.inteligence_organization,
            instance.user.email,
            instance.role,
        ],
    )
    for project in instance.organization.project.all():
        celery_app.send_task(
            "update_user_permission_project",
            args=[
                project.flow_organization,
                instance.user.email,
                instance.role,
            ],
        )


@receiver(post_save, sender=RequestPermissionOrganization)
def request_permission_organization(sender, instance, created, **kwargs):
    if created:
        user = User.objects.filter(email=instance.email)
        if user.exists():
            perm = instance.organization.get_user_authorization(user=user.first())
            perm.role = instance.role
            perm.save(update_fields=["role"])
            instance.delete()
        instance.organization.send_email_invite_organization(email=instance.email)
