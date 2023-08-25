from rest_framework import views, status

from django.conf import settings
from django.http import JsonResponse

from connect.api.v1.internal.flows.flows_rest_client import FlowsRESTClient
from connect.common.models import Project, OrganizationAuthorization, BillingPlan


class UserAPIToken(views.APIView):  # pragma: no cover

    def get(self, request, *args, **kwargs):
        project_uuid = kwargs.get("project_uuid")
        user = request.query_params.get("user")
        project = Project.objects.get(uuid=project_uuid)

        rest_client = FlowsRESTClient()
        response = rest_client.get_user_api_token(str(project.uuid), user)

        return JsonResponse(status=response.status_code, data=response.json())


class UserIsPaying(views.APIView):  # pragma: no cover

    def get(self, request, *args, **kwargs):

        user_email = request.data.get("user_email")
        token = request.data.get("token")
        if token is None:
            token = request.query_params.get("token")
        if user_email is None:
            user_email = request.query_params.get("user_email")

        if token != settings.VERIFICATION_MARKETING_TOKEN:
            return JsonResponse(status=status.HTTP_401_UNAUTHORIZED, data={"message": "You don't have permission to do this action"})

        org_auth = OrganizationAuthorization.objects.filter(user__email=user_email)
        response_data = []
        if len(org_auth) == 0:
            return JsonResponse(status=status.HTTP_404_NOT_FOUND, data={"message": "This user doesn't have permission on any organization"})

        for auth in org_auth:
            current_body = {
                "org_uuid": auth.organization.uuid,
                "is_paying": auth.organization.organization_billing.plan != BillingPlan.PLAN_TRIAL,
                "project": [],
            }
            for project in auth.organization.project.all():
                current_body["project"].append(project.uuid)
            response_data.append({auth.organization.name: current_body})
        return JsonResponse(status=status.HTTP_200_OK, data=dict(orgs=response_data))
