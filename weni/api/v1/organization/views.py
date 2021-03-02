from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from weni.api.v1.metadata import Metadata
from weni.api.v1.mixins import MultipleFieldLookupMixin
from weni.api.v1.organization.filters import OrganizationAuthorizationFilter
from weni.api.v1.organization.permissions import (
    OrganizationHasPermission,
    OrganizationAdminManagerAuthorization,
)
from weni.api.v1.organization.serializers import (
    OrganizationSeralizer,
    OrganizationAuthorizationSerializer,
    OrganizationAuthorizationRoleSerializer,
)
from weni.authentication.models import User
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
            return Organization.objects.none()  # pragma: no cover
        auth = (
            OrganizationAuthorization.objects.exclude(role=0)
            .filter(user=self.request.user)
            .values("organization")
        )
        return self.queryset.filter(pk__in=auth)


class OrganizationAuthorizationViewSet(
    MultipleFieldLookupMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    queryset = OrganizationAuthorization.objects.exclude(
        role=OrganizationAuthorization.ROLE_NOT_SETTED
    )
    serializer_class = OrganizationAuthorizationSerializer
    filter_class = OrganizationAuthorizationFilter
    lookup_fields = ["organization__uuid", "user__username"]
    permission_classes = [IsAuthenticated]

    def get_object(self):
        organization_uuid = self.kwargs.get("organization__uuid")
        user_username = self.kwargs.get("user__username")

        organization = get_object_or_404(Organization, uuid=organization_uuid)
        user = get_object_or_404(User, username=user_username)
        obj = organization.get_user_authorization(user)

        self.check_object_permissions(self.request, obj)
        return obj

    def update(self, *args, **kwargs):
        self.lookup_field = "user__username"

        self.filter_class = None
        self.serializer_class = OrganizationAuthorizationRoleSerializer
        self.permission_classes = [
            IsAuthenticated,
            OrganizationAdminManagerAuthorization,
        ]
        response = super().update(*args, **kwargs)
        instance = self.get_object()
        if instance.role is not OrganizationAuthorization.ROLE_NOT_SETTED:
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
        self.lookup_field = "user__username"
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
        if self.lookup_field not in kwargs:
            return Response(status=405)

        auth = self.get_object()
        auth.delete()
        return Response()
