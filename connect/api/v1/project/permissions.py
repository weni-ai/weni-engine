from rest_framework import permissions

from connect.api.v1 import READ_METHODS, WRITE_METHODS
from connect.common.models import Project, ProjectRole


class ProjectHasPermission(permissions.BasePermission):  # pragma: no cover
    def has_object_permission(self, request, view, obj):
        authorization = obj.organization.get_user_authorization(request.user)
        if request.method in READ_METHODS and not request.user.is_authenticated:
            return authorization.can_read

        if request.user.is_authenticated:
            if request.method in READ_METHODS:
                return authorization.can_read
            if request.method in WRITE_METHODS:
                return authorization.can_write
            return authorization.is_admin
        return False


class IsProjectAdmin(permissions.BasePermission):
    """Checks if the authenticated user is an admin of the project's organization."""

    def has_permission(self, request, view):
        project_uuid = view.kwargs.get("uuid")
        if not project_uuid:
            return False

        try:
            project = Project.objects.select_related("organization").get(
                uuid=project_uuid
            )
        except Project.DoesNotExist:
            return True

        authorization = project.organization.get_user_authorization(request.user)
        return authorization.is_admin


class CanChangeProjectStatus(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False

        authorization = obj.get_user_authorization(request.user)
        role = authorization.role

        if request.method in WRITE_METHODS:
            return role in [ProjectRole.CONTRIBUTOR.value, ProjectRole.MODERATOR.value]

        return False
