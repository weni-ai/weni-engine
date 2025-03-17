from typing import TYPE_CHECKING

from rest_framework import views
from rest_framework.response import Response

from connect.api.v1.internal.permissions import ModuleHasPermission
from connect.api.v1.internal.flows.flows_rest_client import FlowsRESTClient
from .serializers import ExternalServiceSerializer


if TYPE_CHECKING:
    from rest_framework.request import Request


class ExternalServiceAPIView(views.APIView):
    permission_classes = [ModuleHasPermission]

    def post(self, request: "Request") -> Response:

        serializer = ExternalServiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request.data.pop("project")

        project = serializer.validated_data.get("project")

        rest_client = FlowsRESTClient()
        response = rest_client.create_external_service(
            flow_organization=str(project.flow_organization), **request.data
        )
        response.raise_for_status()

        return Response(status=response.status_code, data=response.json())
