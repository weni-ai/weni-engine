from rest_framework import views
from django.http import JsonResponse
from connect.api.v1.internal.flows.flows_rest_client import FlowsRESTClient
from connect.common.models import Project


class UserAPIToken(views.APIView):

    def get(self, request, *args, **kwargs):
        project_uuid = kwargs.get("project_uuid")
        user = request.query_params.get("user")
        project = Project.objects.get(uuid=project_uuid)

        rest_client = FlowsRESTClient()
        response = rest_client.get_user_api_token(str(project.uuid), user)

        return JsonResponse(status=response.status_code, data=response.json())
