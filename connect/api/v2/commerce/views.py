from django.db import transaction
from rest_framework.response import Response
from rest_framework import status
from rest_framework.viewsets import GenericViewSet

from connect.api.v2.commerce.permissions import CanCommunicateInternally
from connect.api.v2.commerce.serializers import CommerceSerializer
from connect.api.v2.organizations.serializers import OrganizationSeralizer
from connect.api.v2.paginations import CustomCursorPagination
from connect.api.v2.projects.serializers import ProjectSerializer
from connect.common.models import Organization
from connect.usecases.users.create import CreateKeycloakUserUseCase
from connect.usecases.users.user_dto import KeycloakUserDTO


class CommerceOrganizationViewSet(GenericViewSet):
    queryset = Organization.objects.all()
    serializer_class = CommerceSerializer
    permission_classes = [CanCommunicateInternally]
    lookup_field = "uuid"
    pagination_class = CustomCursorPagination

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.save()

        response = {
            "organization_uuid": str(data.get("organization").uuid),
            "project_uuid": str(data.get("project").uuid),
        }

        return Response(response, status=status.HTTP_201_CREATED)
