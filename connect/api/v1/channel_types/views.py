from rest_framework import viewsets
from rest_framework.decorators import action

from connect.api.v1.internal.flows.flows_rest_client import FlowsRESTClient

from django.http import JsonResponse


class ChannelTypesViewSet(viewsets.ViewSet):
    """ Viewset for rp-apps channels_types listing and retrieve channels types"""

    @action(
        detail=False,
        methods=["GET"],
        url_name='list-channel-types',
    )
    def list_channel_types(self, request):
        channel_type_code = request.query_params.get('channel_type_code', None)
        rest_client = FlowsRESTClient()
        response = rest_client.list_channel_types(channel_type_code)
        return JsonResponse(status=response.status_code, data=response.json())
