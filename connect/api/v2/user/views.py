from rest_framework import views, status

from django.http import JsonResponse

from connect.api.v1.internal.flows.flows_rest_client import FlowsRESTClient
from connect.common.models import Project, OrganizationAuthorization, BillingPlan
from .permission import HasValidMarketingPermission
from rest_framework.response import Response


class UserAPIToken(views.APIView):  # pragma: no cover

    def get(self, request, *args, **kwargs):
        project_uuid = kwargs.get("project_uuid")
        user = request.query_params.get("user")
        project = Project.objects.get(uuid=project_uuid)

        rest_client = FlowsRESTClient()
        response = rest_client.get_user_api_token(str(project.uuid), user)

        return JsonResponse(status=response.status_code, data=response.json())


class UserIsPaying(views.APIView):

    authentication_classes = []
    permission_classes = [HasValidMarketingPermission]

    def get(self, request, *args, **kwargs):
        user_email = request.query_params.get("user_email")
        if user_email is None:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={"message": "You must provide a user_email"})

        org_auth = OrganizationAuthorization.objects.filter(user__email=user_email)
        response_data = []
        if len(org_auth) == 0:
            return Response(status=status.HTTP_404_NOT_FOUND, data={"message": "This user doesn't have permission on any organization"})

        for auth in org_auth:
            current_body = {
                "org_uuid": auth.organization.uuid,
                "is_paying": auth.organization.organization_billing.plan != BillingPlan.PLAN_TRIAL,
                "project": [project.uuid for project in auth.organization.project.all()],
            }
            response_data.append({auth.organization.name: current_body})
        return Response(status=status.HTTP_200_OK, data=dict(orgs=response_data))
