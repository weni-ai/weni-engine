from rest_framework.permissions import BasePermission
from django.conf import settings


class ProjectsAPITokenPermission(BasePermission):
    """
    Permission class for internal projects API.
    Validates Bearer token from Authorization header against PROJECTS_API_TOKEN setting.
    """
    def has_permission(self, request, view):
        token = request.META.get("HTTP_AUTHORIZATION")
        print("Token: ", token)
        print("Expected token: ", getattr(settings, 'PROJECTS_API_TOKEN', ''))
        if token is None or not token.startswith("Bearer "):
            return False

        expected_token = f"Bearer {getattr(settings, 'PROJECTS_API_TOKEN', '')}"
        return token == expected_token

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)
