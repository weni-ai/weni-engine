from rest_framework.viewsets import GenericViewSet
from rest_framework import mixins

from connect.common.models import Organization, OrganizationAuthorization, OrganizationRole
from connect.api.v2.organizations.serializers import OrganizationSeralizer

from drf_yasg2.utils import swagger_auto_schema
from connect.api.v2.organizations.api_schemas import (
    create_organization_schema,
)

from rest_framework.permissions import IsAuthenticated
from connect.api.v1.organization.permissions import (
    Has2FA,
    OrganizationHasPermission,
)


class OrganizationViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet
):

    queryset = Organization.objects.all()
    serializer_class = OrganizationSeralizer
    lookup_field = "uuid"
    permission_classes = [IsAuthenticated, OrganizationHasPermission, Has2FA]

    def get_queryset(self, *args, **kwargs):
        if getattr(self, "swagger_fake_view", False):
            return Organization.objects.none()  # pragma: no cover

        exclude_roles = [OrganizationRole.NOT_SETTED.value]
        auth = (
            OrganizationAuthorization.objects.exclude(role__in=exclude_roles)
            .filter(user=self.request.user)
            .values("organization")
        )

        return self.queryset.filter(pk__in=auth)

    @swagger_auto_schema(request_body=create_organization_schema)
    def create(self, request, *args, **kwargs):
        return super(OrganizationViewSet, self).create(request, *args, **kwargs)

    def perform_destroy(self, instance):
        # TODO implement soft delete for organization
        user_email = self.request.user.email
        instance.perform_destroy_ai_organization(user_email)
        instance.delete()
