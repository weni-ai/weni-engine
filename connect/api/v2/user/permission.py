from rest_framework.permissions import BasePermission
from django.conf import settings


class HasValidMarketingPermission(BasePermission):
    def has_permission(self, request, view):
        token = request.META.get("HTTP_AUTHORIZATION")
        if token is None or not token.startswith("Bearer "):
            return False

        return token == settings.VERIFICATION_MARKETING_TOKEN

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)
