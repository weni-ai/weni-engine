from django.utils import timezone
from rest_framework import mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import GenericViewSet

from weni.api.v1.dashboard.filters import StatusServiceFilter
from weni.api.v1.dashboard.serializers import (
    NewsletterSerializer,
    StatusServiceSerializer,
)
from weni.common.models import ServiceStatus, NewsletterLanguage


class NewsletterViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet
):
    """
    List all newsletter.
    """

    serializer_class = NewsletterSerializer
    queryset = NewsletterLanguage.objects
    permission_classes = [IsAuthenticated]

    def get_queryset(self, *args, **kwargs):
        if getattr(self, "swagger_fake_view", False):
            # queryset just for schema generation metadata
            return NewsletterLanguage.objects.none()

        return self.queryset.filter(
            newsletter__created_at__gt=timezone.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            - timezone.timedelta(days=90)
        ).filter(language=self.request.user.language)


class StatusServiceViewSet(mixins.ListModelMixin, GenericViewSet):
    """
    List all status service.
    """

    serializer_class = StatusServiceSerializer
    queryset = ServiceStatus.objects.all()
    filter_class = StatusServiceFilter
    permission_classes = [IsAuthenticated]
