from django.shortcuts import get_object_or_404
from rest_framework import permissions

from connect.api.v1 import READ_METHODS, WRITE_METHODS
from connect.common.models import Organization, OrganizationAuthorization, Project
from connect.usecases.organizations.sso_access import (
    EvaluateOrganizationSSOAccessUseCase,
)
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


class HasSSOAccess(permissions.BasePermission):
    """Blocks deep links into SSO-enforcing organizations the current session
    does not comply with. List/retrieve organization metadata remains readable;
    disability is expressed via access_status fields."""

    SSO_ENFORCED_ORG_READ_ACTIONS = frozenset(
        {
            "get_contact_active",
            "get_contacts_active_per_project",
        }
    )

    def has_permission(self, request, view):
        organization_uuid = request.query_params.get("organization")
        if organization_uuid:
            organization = get_object_or_404(Organization, uuid=organization_uuid)
            return self._is_compliant(request, organization)

        if view and hasattr(view, "kwargs"):
            organization_uuid = view.kwargs.get("organization_uuid")
            if organization_uuid:
                organization = get_object_or_404(Organization, uuid=organization_uuid)
                return self._is_compliant(request, organization)

            if request.method in WRITE_METHODS:
                organization_uuid = view.kwargs.get("organization__uuid")
                if organization_uuid:
                    organization = get_object_or_404(
                        Organization, uuid=organization_uuid
                    )
                    return self._is_compliant(request, organization)

            candidate_uuid = view.kwargs.get("uuid")
            if candidate_uuid:
                return self._evaluate_uuid_kwarg(request, view, candidate_uuid)

        if request.method in WRITE_METHODS:
            organization_uuid = self._organization_uuid_from_write_body(request)
            if organization_uuid:
                organization = get_object_or_404(Organization, uuid=organization_uuid)
                return self._is_compliant(request, organization)

        return True

    def _evaluate_uuid_kwarg(self, request, view, candidate_uuid):
        organization = Organization.objects.filter(uuid=candidate_uuid).first()
        if organization:
            if request.method in READ_METHODS:
                return self._allows_organization_read(request, view, organization)
            return self._is_compliant(request, organization)

        project = (
            Project.objects.select_related("organization")
            .filter(uuid=candidate_uuid)
            .first()
        )
        if project:
            return self._is_compliant(request, project.organization)

        return True

    def _organization_uuid_from_write_body(self, request):
        try:
            organization_uuid = request.data.get("organization")
            if isinstance(organization_uuid, str) and organization_uuid:
                return organization_uuid
        except Exception:
            pass

        underlying = getattr(request, "_request", request)
        organization_uuid = getattr(underlying, "POST", {}).get("organization")
        if isinstance(organization_uuid, str) and organization_uuid:
            return organization_uuid
        return None

    def has_object_permission(self, request, view, obj):
        if isinstance(obj, Organization):
            if request.method in READ_METHODS:
                return self._allows_organization_read(request, view, obj)
            organization = obj
        elif isinstance(obj, Project):
            organization = obj.organization
        elif isinstance(obj, OrganizationAuthorization):
            if request.method in READ_METHODS:
                return True
            organization = obj.organization
        else:
            return True
        return self._is_compliant(request, organization)

    def _allows_organization_read(self, request, view, organization):
        if not getattr(view, "sso_allow_read_without_compliance", True):
            return self._is_compliant(request, organization)
        if getattr(view, "action", None) in self.SSO_ENFORCED_ORG_READ_ACTIONS:
            return self._is_compliant(request, organization)
        return True

    def _is_compliant(self, request, organization):
        session_identity_provider = getattr(request, "session_identity_provider", None)
        return EvaluateOrganizationSSOAccessUseCase().execute(
            organization=organization,
            user=request.user,
            session_identity_provider=session_identity_provider,
        )


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
