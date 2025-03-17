from django.utils import timezone
from rest_framework import mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response

from connect.api.v1.dashboard.filters import StatusServiceFilter
from connect.api.v1.dashboard.serializers import (
    NewsletterSerializer,
    StatusServiceSerializer,
    NewsletterOrganizationSerializer,
)
from connect.common.models import (
    ServiceStatus,
    NewsletterLanguage,
    NewsletterOrganization,
)
from itertools import chain


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

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        user = self.request.user

        organization_newsletters = NewsletterOrganization.objects.filter(
            organization__authorizations__user=user
        ).filter(
            newsletter__created_at__gt=timezone.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            - timezone.timedelta(days=90)
        )

        serializer = self.get_serializer(queryset, many=True)
        nl_org_serializer = NewsletterOrganizationSerializer(
            organization_newsletters, many=True
        )

        language_newsletters = serializer.data
        organization_newsletters = nl_org_serializer.data

        newsletters = list(chain(language_newsletters, organization_newsletters))
        return Response(newsletters)


class StatusServiceViewSet(mixins.ListModelMixin, GenericViewSet):
    """
    List all status service.
    """

    serializer_class = StatusServiceSerializer
    queryset = ServiceStatus.objects.all()
    filter_class = StatusServiceFilter
    permission_classes = [IsAuthenticated]
