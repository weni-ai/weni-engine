from rest_framework import mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import GenericViewSet

from connect.api.v1.newsletter.serializers import DashboardNewsletterSerializer
from connect.common.models import DashboardNewsletter


class DashboardNewsletterViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet
):
    """
    List all newsletter.
    """

    serializer_class = DashboardNewsletterSerializer
    queryset = DashboardNewsletter.objects.all()
    permission_classes = [IsAuthenticated]
