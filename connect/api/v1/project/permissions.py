from rest_framework import permissions

from connect.api.v1 import READ_METHODS, WRITE_METHODS


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
            return authorization.is_moderator
        return False


class ModuleHasPermission(permissions.BasePermission):  # pragma: no cover

    def has_permission(self, request, view):
        return request.user.has_perm("authentication.can_communicate_internally")

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)
