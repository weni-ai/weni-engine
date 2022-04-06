import email
import logging

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from connect.authentication.models import User
from connect.common.models import (
    Project,
    Service,
    Organization,
    OrganizationAuthorization,
    RequestPermissionOrganization,
    OrganizationLevelRole,
    OrganizationRole,
    RequestPermissionProject,
    ProjectAuthorization,
    ProjectRoleLevel,
    RocketAuthorization,
    RequestRocketPermission,
)
from connect.celery import app as celery_app
from connect.common.gateways.rocket_gateway import Rocket

logger = logging.getLogger("connect.common.signals")


@receiver(post_save, sender=Project)
def create_service_status(sender, instance, created, **kwargs):
    if created:
        for service in Service.objects.filter(default=True):
            instance.service_status.create(service=service)

        for permission in instance.project_authorizations.all():
            celery_app.send_task(
                "update_user_permission_project",
                args=[
                    instance.flow_organization,
                    instance.uuid,
                    permission.user.email,
                    permission.role,
                ],
            )
        for authorization in instance.organization.authorizations.all():
            if authorization.can_contribute:
                project_auth = instance.get_user_authorization(authorization.user)
                project_auth.role = authorization.role
                project_auth.save()


@receiver(post_save, sender=Service)
def create_service_default_in_all_user(sender, instance, created, **kwargs):
    if created and instance.default:
        for project in Project.objects.all():
            project.service_status.create(service=instance)


@receiver(post_delete, sender=Organization)
def delete_organization(instance, **kwargs):
    for authorization in instance.authorizations.all():
        instance.send_email_delete_organization(
            first_name=authorization.user.first_name, email=authorization.user.email
        )


@receiver(post_save, sender=Organization)
def update_organization(instance, **kwargs):
    for project in instance.project.all():
        celery_app.send_task(  # pragma: no cover
            name="update_suspend_project",
            args=[
                str(project.flow_organization),
                instance.is_suspended,
            ],
        )


@receiver(post_save, sender=OrganizationAuthorization)
def org_authorizations(sender, instance, **kwargs):
    if instance.role is not OrganizationLevelRole.NOTHING.value:
        celery_app.send_task(
            "update_user_permission_organization",
            args=[
                instance.organization.inteligence_organization,
                instance.user.email,
                instance.role,
            ],
        )


@receiver(post_delete, sender=OrganizationAuthorization)
def delete_authorizations(instance, **kwargs):
    instance.organization.send_email_remove_permission_organization(
        first_name=instance.user.first_name, email=instance.user.email
    )


@receiver(post_save, sender=RequestPermissionOrganization)
def request_permission_organization(sender, instance, created, **kwargs):
    if created:
        user = User.objects.filter(email=instance.email)
        if user.exists():
            perm = instance.organization.get_user_authorization(user=user.first())
            perm.role = instance.role
            perm.save(update_fields=["role"])
            if perm.can_contribute:
                for proj in instance.organization.project.all():
                    proj.project_authorizations.create(
                        user=user.first(),
                        role=perm.role,
                        organization_authorization=perm,
                    )
            instance.delete()
        instance.organization.send_email_invite_organization(email=instance.email)


@receiver(post_save, sender=RequestPermissionProject)
def request_permission_project(sender, instance, created, **kwargs):
    if created:
        user = User.objects.filter(email=instance.email)
        if user.exists():
            user = user.first()
            org = instance.project.organization
            auth = instance.project.project_authorizations
            auth_user = auth.filter(user=user)
            org_auth = org.authorizations.filter(user__email=user.email)

            if not org_auth.exists():
                org_auth = org.authorizations.create(
                    user=user, role=OrganizationRole.VIEWER.value
                )
            else:
                org_auth = org_auth.first()

            if not auth_user.exists():
                ProjectAuthorization.objects.create(
                    user=user,
                    project=instance.project,
                    organization_authorization=org_auth,
                    role=instance.role,
                )
            else:
                auth_user = auth_user.first()
                auth_user.role = instance.role
                auth_user.save(update_fields=["role"])
            instance.delete()
        # todo: send invite project email


@receiver(post_save, sender=ProjectAuthorization)
def project_authorization(sender, instance, created, **kwargs):
    if instance.role is not ProjectRoleLevel.NOTHING.value:
        instance_user = (
            instance.organization_authorization.organization.get_user_authorization(
                instance.user
            )
        )
        if instance_user.level == OrganizationLevelRole.NOTHING.value:
            instance_user.role = OrganizationRole.VIEWER.value
            instance_user.save(update_fields=["role"])

        celery_app.send_task(
            "update_user_permission_project",
            args=[
                instance.project.flow_organization,
                instance.project.uuid,
                instance.user.email,
                instance.role,
            ],
        )


@receiver(post_save, sender=RequestRocketPermission)
def request_rocket_permission(sender, instance, created, **kwargs):
    if created:
        user = User.objects.filter(email=instance.email)
        if user.exists():
            user = user.first()
            project_auth = instance.project.project_authorizations.filter(user=user)
            if project_auth.exists():
                project_auth = project_auth.first()
                if not project_auth.rocket_authorization:
                    project_auth.rocket_authorization = (
                        RocketAuthorization.objects.create(role=instance.role)
                    )
                else:
                    project_auth.rocket_authorization.role = instance.role
                project_auth.save(update_fields=["rocket_authorization"])
                project_auth.rocket_authorization.update_rocket_permission()
            instance.delete()
