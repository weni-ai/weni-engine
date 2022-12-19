from rest_framework import views
from rest_framework.decorators import action
from rest_framework import mixins, permissions

from connect.api.v1.internal.flows.flows_rest_client import FlowsRESTClient

from django.http import JsonResponse

class ChannelTypesAPIView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """ Returns rapidpro channel listing and detail """
        channel_type_code = request.query_params.get('channel_type_code', None)
        rest_client = FlowsRESTClient()
        response = rest_client.list_channel_types(channel_type_code)
        return JsonResponse(status=response.status_code, data=response.json())
