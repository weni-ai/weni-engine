from rest_framework import permissions

from connect.api.v1 import READ_METHODS, WRITE_METHODS
from connect.common.models import ProjectRole


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


class CanChangeProjectStatus(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
        
        authorization = obj.get_user_authorization(request.user)
        role = authorization.role

        if request.method in WRITE_METHODS:
            return role in [ProjectRole.CONTRIBUTOR.value, ProjectRole.MODERATOR.value]

        return False
