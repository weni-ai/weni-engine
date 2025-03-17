import json

from rest_framework import views
from rest_framework.response import Response

from connect.common.models import Organization, Project
from connect.api.v2.internals.serializers import (
    OrganizationAISerializer,
    CustomParameterSerializer,
    InternalProjectSerializer,
)
from connect.api.v1.internal.permissions import ModuleHasPermission

from django.shortcuts import get_object_or_404

from drf_yasg2.utils import swagger_auto_schema
from rest_framework.viewsets import ModelViewSet


class InternalProjectViewSet(ModelViewSet):
    permission_classes = [ModuleHasPermission]
    queryset = Project.objects.all()
    lookup_field = "uuid"
    serializer_class = InternalProjectSerializer


class AIGetOrganizationView(views.APIView):
    permission_classes = [ModuleHasPermission]

    @swagger_auto_schema(
        operation_description="GET /v2/internals/connect/organizations?project_uuid={uuid}",
        query_serializer=CustomParameterSerializer,
    )
    def get(self, request, **kwargs):
        """Get organization data using proejct_uuid"""

        uuid = request.query_params.get("project_uuid")
        organization = get_object_or_404(Organization, project__uuid=uuid)
        serializer = OrganizationAISerializer(organization)

        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="PATCH /v2/internals/connect/organizations?project_uuid={uuid}",
        query_serializer=CustomParameterSerializer,
    )
    def patch(self, request, **kwargs):
        uuid = request.query_params.get("project_uuid")
        if type(request.data) == str:
            data = json.loads(request.data)
            intelligence_organization = data.get("intelligence_organization")
        else:
            intelligence_organization = request.data.get("intelligence_organization")

        organization = get_object_or_404(Organization, project__uuid=uuid)
        organization.inteligence_organization = int(intelligence_organization)
        organization.save(update_fields=["inteligence_organization"])

        response = {
            "organization": {
                "intellgence_organization": organization.inteligence_organization,
                "uuid": organization.uuid,
            }
        }

        return Response(response)
