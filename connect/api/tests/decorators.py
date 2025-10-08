import functools

from connect.common.models import (
    OrganizationAuthorization,
    OrganizationRole,
    ProjectAuthorization,
    ProjectRole,
)


def with_project_auth(role=ProjectRole.NOT_SETTED.value):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            project = self.project
            user = self.user

            organization_authorization = OrganizationAuthorization.objects.filter(
                organization=project.organization, user=user
            ).first()
            ProjectAuthorization.objects.create(
                project=project,
                user=user,
                role=role,
                organization_authorization=organization_authorization,
            )

            return func(self, *args, **kwargs)

        return wrapper

    return decorator


def with_organization_auth(role=OrganizationRole.NOT_SETTED.value):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            organization = self.organization
            user = self.user

            OrganizationAuthorization.objects.create(
                organization=organization, user=user, role=role
            )

            return func(self, *args, **kwargs)

        return wrapper

    return decorator
