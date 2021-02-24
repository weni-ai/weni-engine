from rest_framework import mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import GenericViewSet

from weni.api.v1.metadata import Metadata
from weni.api.v1.organization.permissions import OrganizationHasPermission
from weni.api.v1.organization.serializers import OrganizationSeralizer
from weni.common.models import Organization, OrganizationAuthorization


class OrganizationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSeralizer
    permission_classes = [IsAuthenticated, OrganizationHasPermission]
    lookup_field = "uuid"
    metadata_class = Metadata

    def get_queryset(self, *args, **kwargs):
        if getattr(self, "swagger_fake_view", False):
            # queryset just for schema generation metadata
            return Organization.objects.none()
        auth = (
            OrganizationAuthorization.objects.exclude(role=0)
            .filter(user=self.request.user)
            .values("organization")
        )
        return self.queryset.filter(owner__in=auth)
