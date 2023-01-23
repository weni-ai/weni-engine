from rest_framework import views
from rest_framework.response import Response

from connect.common.models import Organization
from connect.api.v2.internals.serializers import (
    OrganizationAISerializer,
    CustomParameterSerializer,
)
from connect.api.v1.internal.permissions import ModuleHasPermission

from django.shortcuts import get_object_or_404

from drf_yasg2.utils import swagger_auto_schema


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
