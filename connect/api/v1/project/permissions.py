from django.contrib.auth import get_user_model
from rest_framework import permissions
from weni_commons.auth import get_project_uuid, get_user_email

from connect.api.v1 import READ_METHODS, WRITE_METHODS
from connect.common.exceptions import OrganizationAuthorizationException
from connect.common.models import Project, ProjectRole

User = get_user_model()


class ProjectHasPermission(permissions.BasePermission):  # pragma: no cover
    def has_object_permission(self, request, view, obj):
        try:
            authorization = obj.organization.get_user_authorization(request.user)
        except OrganizationAuthorizationException:
            return False
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
        project_uuid = get_project_uuid(request)
        if not project_uuid:
            return False

        user = self._resolve_user(request)
        if user is None:
            return False

        try:
            project = Project.objects.select_related("organization").get(
                uuid=project_uuid
            )
        except Project.DoesNotExist:
            return True

        try:
            authorization = project.organization.get_user_authorization(user)
        except OrganizationAuthorizationException:
            return False
        return authorization.is_admin

    def _resolve_user(self, request):
        """Return the user whose organization role must be inspected.

        Keycloak callers already carry a Django user on the request. JWT callers
        are authenticated as a lightweight principal with no Django row, so the
        user is looked up by the email the auth context exposes — a claim of a
        signature-verified token, never spoofable request data.
        """
        if getattr(request.user, "pk", None) is not None:
            return request.user

        email = get_user_email(request)
        return User.objects.filter(email=email).first() if email else None


class CanChangeProjectStatus(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False

        authorization = obj.get_user_authorization(request.user)
        role = authorization.role

        if request.method in WRITE_METHODS:
            return role in [ProjectRole.CONTRIBUTOR.value, ProjectRole.MODERATOR.value]

        return False
