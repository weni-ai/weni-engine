from rest_framework import mixins, status
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_yasg2.utils import swagger_auto_schema

from connect.common.models import (
    Organization,
    OrganizationAuthorization,
    OrganizationRole
)
from connect.api.v1.organization.permissions import (
    Has2FA,
    OrganizationHasPermission,
)
from connect.api.v2.organizations.serializers import (
    OrganizationSeralizer,
    NestedAuthorizationOrganizationSerializer
)
from connect.api.v2.projects.serializers import ProjectSerializer
from connect.api.v2.organizations.api_schemas import (
    create_organization_schema,
)
from connect.api.v2.paginations import CustomCursorPagination


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
    pagination_class = CustomCursorPagination

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
        org_data = request.data.get("organization")
        project_data = request.data.get("project")

        # Organization
        serializer = self.get_serializer(data=org_data)
        serializer.is_valid()
        instance = serializer.save()

        if type(instance) == dict:
            return Response(**instance)

        # Project
        project_data.update(
            {"organization": instance.uuid}
        )
        project_serializer = ProjectSerializer(data=project_data, context={"request": request})
        project_serializer.is_valid()
        project_instance = project_serializer.save()

        if type(project_instance) == dict:
            instance.delete()
            return Response(**project_instance)

        data = {
            "organization": serializer.data,
            "project": project_serializer.data
        }

        return Response(data, status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        # TODO implement soft delete for organization
        user_email = self.request.user.email
        instance.perform_destroy_ai_organization(user_email)
        instance.delete()


class OrganizationAuthorizationViewSet(
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    queryset = Organization.objects
    permission_classes = [IsAuthenticated, OrganizationHasPermission]
    lookup_field = "uuid"

    def get_serializer_class(self):
        return NestedAuthorizationOrganizationSerializer
