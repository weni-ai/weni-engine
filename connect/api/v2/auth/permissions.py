from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from weni_commons.auth import WeniAuthContext

TARGET_USER_QUERY_PARAM = "user"
INTERNAL_COMMUNICATION_PERMISSION = "authentication.can_communicate_internally"
OTHER_USERS_ACCESS_DENIED = "You do not have permission to access other users' data"


class CanResolveTargetUser(BasePermission):
    """Authorize resolving another user's authorization via ``?user=``.

    Looking up a user other than the caller is restricted to trusted callers:
    an inter-module JWT service, or a Keycloak user holding the
    internal-communication permission. Requests that omit ``?user=`` resolve the
    caller's own identity and are always allowed.
    """

    message = OTHER_USERS_ACCESS_DENIED

    def has_permission(self, request: Request, view) -> bool:
        if not request.query_params.get(TARGET_USER_QUERY_PARAM):
            return True

        auth = request.auth
        if isinstance(auth, WeniAuthContext) and auth.is_jwt:
            return True

        return request.user.has_perm(INTERNAL_COMMUNICATION_PERMISSION)
