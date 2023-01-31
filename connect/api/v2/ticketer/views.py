from rest_framework import views, status
from django.conf import settings
from django.http import JsonResponse
from connect.api.v1.internal.permissions import ModuleHasPermission
from connect.api.v1.internal.flows.flows_rest_client import FlowsRESTClient
from connect.common.models import Project


class TicketerAPIView(views.APIView):
    permission_classes = [ModuleHasPermission]

    def post(self, request, *args, **kwargs):
        project_uuid = kwargs.get("project_uuid")
        ticketer_type = request.data.get("ticketer_type")
        name = request.data.get("name")
        config = request.data.get("config")

        project = Project.objects.get(uuid=project_uuid)

        if not settings.TESTING:
            flows_client = FlowsRESTClient()
            ticketer = flows_client.create_ticketer(
                project_uuid=str(project.flow_organization),
                ticketer_type=ticketer_type,
                name=name,
                config=config,
            )
            return JsonResponse(status=status.HTTP_200_OK, data=ticketer)
