from rest_framework import mixins, permissions
from rest_framework.viewsets import GenericViewSet

from weni.api.v1.account.serializers import UserSerializer
from weni.authentication.models import User


class MyUserProfileViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    """
    Manager current user profile.
    retrieve:
    Get current user profile
    update:
    Update current user profile.
    partial_update:
    Update, partially, current user profile.
    """

    serializer_class = UserSerializer
    queryset = User.objects
    lookup_field = None
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, *args, **kwargs):
        request = self.request
        user = request.user

        # May raise a permission denied
        self.check_object_permissions(self.request, user)

        return user
