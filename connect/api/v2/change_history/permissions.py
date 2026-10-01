from rest_framework.permissions import BasePermission

from connect.common.models import ProjectAuthorization, ProjectRole


class HasProjectPermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        return ProjectAuthorization.objects.filter(
            project__uuid=view.kwargs.get("project_uuid"),
            user=request.user,
            role__gt=ProjectRole.NOT_SETTED.value,
        ).exists()
