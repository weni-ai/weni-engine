from django.shortcuts import get_object_or_404
from rest_framework import permissions

from connect.api.v1 import READ_METHODS, WRITE_METHODS
from connect.common.models import Organization, Project
from django.conf import settings


class OrganizationHasPermission(permissions.BasePermission):  # pragma: no cover
    def has_object_permission(self, request, view, obj):
        authorization = obj.get_user_authorization(request.user)
        if request.method in READ_METHODS and not request.user.is_authenticated:
            return authorization.can_read

        if request.user.is_authenticated:
            if request.method in READ_METHODS:
                return authorization.can_read
            if request.method in WRITE_METHODS:
                return authorization.can_write
            return authorization.is_admin
        return False


class OrganizationAdminManagerAuthorization(
    permissions.BasePermission
):  # pragma: no cover
    def has_object_permission(self, request, view, obj):
        authorization = obj.organization.get_user_authorization(request.user)
        return authorization.is_admin


class OrganizationHasPermissionBilling(permissions.BasePermission):
    def has_permission(self, request, view):
        # if the request pass organization uuid in query params else call has_object_permission
        uuid = request.query_params.get("organization")
        if uuid:
            obj = Organization.objects.get(uuid=uuid)
            return self.has_object_permission(request, view, obj)
        return True

    def has_object_permission(self, request, view, obj):
        authorization = obj.get_user_authorization(request.user)
        return authorization.can_contribute_billing


class Has2FA(permissions.BasePermission):
    def has_permission(self, request, view):
        uuid = request.query_params.get("organization")
        if uuid:
            organization = get_object_or_404(Organization, uuid=uuid)

            if organization.enforce_2fa:
                auth = organization.get_user_authorization(request._user)
                return auth.has_2fa
            else:
                # return true to pass this permisson check and verify others
                return True
        return True

    def has_object_permission(self, request, view, obj):
        if isinstance(obj, Organization):
            org = obj
        elif isinstance(obj, Project):
            org = obj.organization

        if org.enforce_2fa:
            auth = org.get_user_authorization(request.user)
            return auth.has_2fa
        else:
            return True


def _is_orm_user(user):
    if not settings.ALLOW_CRM_ACCESS:
        return False

    if user.email not in settings.CRM_EMAILS_LIST:
        return False

    return True


class IsCRMUser(permissions.IsAuthenticated):
    def has_permission(self, request, view) -> bool:
        is_authenticated = super().has_permission(request, view)

        if not is_authenticated:
            return False

        return _is_orm_user(request.user)

    def has_object_permission(self, request, view, obj):
        return _is_orm_user(request.user)


class HasExternalProviderAccess(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.require_external_provider_for_access and (
            request.user.identity_provider.exists() or bool(request.user.password)
        )
