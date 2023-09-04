from rest_framework import permissions
from django.shortcuts import get_object_or_404
from connect.common.models import Organization


class OrgIPPermission(permissions.BasePermission):  # pragma: no cover
    def has_object_permission(self, request, view, obj):
        ip = request.META.get("REMOTE_ADDR")
        allowed_ips = obj.allowed_ips
        if allowed_ips:
            return ip in allowed_ips
        return True

class ProjectIPPermission(permissions.BasePermission):  # pragma: no cover
    def has_object_permission(self, request, view, obj):
        ip = request.META.get("REMOTE_ADDR")
        organization = obj.organization
        allowed_ips = organization.allowed_ips
        if allowed_ips:
            return ip in allowed_ips
        return True
    
    def has_permission(self, request, view):
        import pprint
        uuid = request.parser_context.get("kwargs").get("organization_uuid")
        organization = get_object_or_404(Organization, uuid=uuid)
        ip = request.META.get("REMOTE_ADDR")
        allowed_ips = organization.allowed_ips
        if allowed_ips:
            return ip in allowed_ips
        return True
        
    #     return True
        # authorization = obj.get_user_authorization(request.user)
        # if request.method in READ_METHODS and not request.user.is_authenticated:
        #     return authorization.can_read

        # if request.user.is_authenticated:
        #     if request.method in READ_METHODS:
        #         return authorization.can_read
        #     if request.method in WRITE_METHODS:
        #         return authorization.can_write
        #     return authorization.is_admin
        # return False