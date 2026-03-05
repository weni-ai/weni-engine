import logging

from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework.mixins import CreateModelMixin

from connect.api.v2.commerce.permissions import CanCommunicateInternally
from connect.api.v2.commerce.serializers import (
    CommerceSerializer,
    CreateVtexProjectSerializer,
    SetVtexHostStoreSerializer,
    SuspendVtexProjectSerializer,
)
from connect.api.v2.paginations import CustomCursorPagination
from connect.common.models import Organization, Project
from connect.usecases.commerce.create_vtex_project import CreateVtexProjectUseCase
from connect.usecases.commerce.dto import CreateVtexProjectDTO, SuspendVtexProjectDTO
from connect.usecases.commerce.set_vtex_host_store import SetVtexHostStoreUseCase
from connect.usecases.commerce.suspend_vtex_project import SuspendVtexProjectUseCase

logger = logging.getLogger(__name__)


class CommerceOrganizationViewSet(CreateModelMixin, GenericViewSet):
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


class CreateVtexProjectView(views.APIView):
    permission_classes = [CanCommunicateInternally]

    def post(self, request):
        serializer = CreateVtexProjectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        dto = CreateVtexProjectDTO(**serializer.validated_data)
        result = CreateVtexProjectUseCase().execute(dto)

        return Response(result, status=status.HTTP_200_OK)


class SuspendVtexProjectView(views.APIView):
    permission_classes = [CanCommunicateInternally]

    def post(self, request, project_uuid):
        serializer = SuspendVtexProjectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        dto = SuspendVtexProjectDTO(
            project_uuid=project_uuid,
            conversation_limit=serializer.validated_data["conversation_limit"],
        )

        try:
            result = SuspendVtexProjectUseCase().execute(dto)
        except Project.DoesNotExist:
            return Response(
                {"detail": "Project not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(result, status=status.HTTP_200_OK)


class SetVtexHostStoreView(views.APIView):
    permission_classes = [CanCommunicateInternally]

    def patch(self, request, project_uuid):
        serializer = SetVtexHostStoreSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = SetVtexHostStoreUseCase().execute(
                project_uuid=project_uuid,
                vtex_host_store=serializer.validated_data["vtex_host_store"],
            )
        except Project.DoesNotExist:
            return Response(
                {"detail": "Project not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(result, status=status.HTTP_200_OK)
