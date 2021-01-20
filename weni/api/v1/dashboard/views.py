from django.db.models import Q
from rest_framework import mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import GenericViewSet

from weni.api.v1.dashboard.serializers import (
    NewsletterSerializer,
    StatusServiceSerializer,
    DashboardInfoSerializer,
)
from weni.authentication.models import User
from weni.common.models import Newsletter, ServiceStatus


class NewsletterViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet
):
    """
    List all newsletter.
    """

    serializer_class = NewsletterSerializer
    queryset = Newsletter.objects.all()
    permission_classes = [IsAuthenticated]


class StatusServiceViewSet(mixins.ListModelMixin, GenericViewSet):
    """
    List all status service.
    """

    serializer_class = StatusServiceSerializer
    queryset = ServiceStatus.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self, *args, **kwargs):
        return self.queryset.filter(
            Q(user=self.request.user) | Q(service__default=True)
        )


class DashboardInfoViewSet(mixins.RetrieveModelMixin, GenericViewSet):
    """
    Manager Dashboard
    """

    serializer_class = DashboardInfoSerializer
    queryset = User.objects
    lookup_field = None
    permission_classes = [IsAuthenticated]

    def get_object(self, *args, **kwargs):
        request = self.request
        user = request.user

        # May raise a permission denied
        self.check_object_permissions(self.request, user)

        return user
