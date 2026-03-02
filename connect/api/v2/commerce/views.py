from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework.mixins import CreateModelMixin

from connect.api.v2.commerce.permissions import CanCommunicateInternally
from connect.api.v2.commerce.serializers import (
    CommerceSerializer,
    CreateVtexProjectSerializer,
)
from connect.api.v2.paginations import CustomCursorPagination
from connect.common.models import Organization
from connect.usecases.commerce.create_vtex_project import CreateVtexProjectUseCase
from connect.usecases.commerce.dto import CreateVtexProjectDTO


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
