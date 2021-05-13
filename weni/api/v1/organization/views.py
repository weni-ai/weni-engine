from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from weni.celery import app as celery_app
from weni.api.v1.metadata import Metadata
from weni.api.v1.mixins import MultipleFieldLookupMixin
from weni.api.v1.organization.filters import (
    OrganizationAuthorizationFilter,
    RequestPermissionOrganizationFilter,
)
from weni.api.v1.organization.permissions import (
    OrganizationHasPermission,
    OrganizationAdminManagerAuthorization,
)
from weni.api.v1.organization.serializers import (
    OrganizationSeralizer,
    OrganizationAuthorizationSerializer,
    OrganizationAuthorizationRoleSerializer,
    RequestPermissionOrganizationSerializer,
)
from weni.authentication.models import User
from weni.common.models import (
    Organization,
    OrganizationAuthorization,
    RequestPermissionOrganization,
)


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
            return Organization.objects.none()  # pragma: no cover
        auth = (
            OrganizationAuthorization.objects.exclude(role=0)
            .filter(user=self.request.user)
            .values("organization")
        )
        return self.queryset.filter(pk__in=auth)

    def perform_destroy(self, instance):
        inteligence_organization = instance.inteligence_organization
        instance.delete()

        celery_app.send_task(
            "delete_organization",
            args=[inteligence_organization, self.request.user.email],
        )


class OrganizationAuthorizationViewSet(
    MultipleFieldLookupMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    queryset = OrganizationAuthorization.objects
    serializer_class = OrganizationAuthorizationSerializer
    filter_class = OrganizationAuthorizationFilter
    lookup_fields = ["organization__uuid", "user__id"]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = [
        "=user__first_name",
        "^user__first_name",
        "$user__first_name",
        "=user__last_name",
        "^user__last_name",
        "$user__last_name",
        "=user__last_name",
        "^user__username",
        "$user__username",
        "=user__email",
        "^user__email",
        "$user__email",
    ]
    permission_classes = [IsAuthenticated]

    def get_object(self):
        organization_uuid = self.kwargs.get("organization__uuid")
        user_id = self.kwargs.get("user__id")

        organization = get_object_or_404(Organization, uuid=organization_uuid)
        user = get_object_or_404(User, pk=user_id)
        obj = organization.get_user_authorization(user)

        self.check_object_permissions(self.request, obj)
        return obj

    def update(self, *args, **kwargs):
        self.lookup_field = "user__id"

        self.filter_class = None
        self.serializer_class = OrganizationAuthorizationRoleSerializer
        self.permission_classes = [
            IsAuthenticated,
            OrganizationAdminManagerAuthorization,
        ]
        response = super().update(*args, **kwargs)
        instance = self.get_object()
        instance.send_new_role_email(self.request.user)
        return response

    def list(self, request, *args, **kwargs):
        self.lookup_fields = []
        return super().list(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self.permission_classes = [
            IsAuthenticated,
            OrganizationAdminManagerAuthorization,
        ]
        self.filter_class = None
        self.lookup_field = "user__id"
        return super().destroy(request, *args, **kwargs)

    @action(
        detail=True,
        methods=["DELETE"],
        url_name="organization-remove-my-user",
        lookup_fields=["organization__uuid", "user__username"],
    )
    def remove_my_user(self, request, **kwargs):  # pragma: no cover
        """
        Delete my user authorization
        """
        organization_uuid = self.kwargs.get("organization__uuid")

        organization = get_object_or_404(Organization, uuid=organization_uuid)
        obj = organization.get_user_authorization(self.request.user)

        self.check_object_permissions(self.request, obj)

        obj.delete()
        return Response(status=204)


class RequestPermissionOrganizationViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    queryset = RequestPermissionOrganization.objects
    serializer_class = RequestPermissionOrganizationSerializer
    permission_classes = [IsAuthenticated, OrganizationAdminManagerAuthorization]
    filter_class = RequestPermissionOrganizationFilter
    metadata_class = Metadata
