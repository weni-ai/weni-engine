from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import GenericViewSet

from weni.api.v1.dashboard.serializers import (
    NewsletterSerializer,
    StatusServiceSerializer,
)
from weni.common.models import Newsletter, ServiceStatus


class NewsletterViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet
):
    """
    List all newsletter.
    """

    serializer_class = NewsletterSerializer
    queryset = Newsletter.objects.filter(
        created_at__gt=timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        - timezone.timedelta(days=90)
    )
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
            (
                Q(project__organization__authorizations__user=self.request.user)
                & Q(service__default=True)
            )
            | Q(project__organization__authorizations__user=self.request.user)
        )
