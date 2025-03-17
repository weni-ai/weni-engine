from rest_framework import views
from rest_framework.response import Response

from connect.api.v1.internal.permissions import ModuleHasPermission
from connect.api.v1.internal.flows.flows_rest_client import FlowsRESTClient


class ChannelTypesAPIView(views.APIView):
    permission_classes = [ModuleHasPermission]

    def get(self, request):
        """Returns rapidpro channel listing and detail"""
        channel_type_code = request.query_params.get("channel_type_code", None)
        rest_client = FlowsRESTClient()
        response = rest_client.list_channel_types(channel_type_code)
        if response.status_code == 200:
            return Response(status=response.status_code, data=response.json())

        return Response(status=response.status_code, data=response)
