from rest_framework import views, status
from django.http import JsonResponse
from connect.api.v1.internal.flows.flows_rest_client import FlowsRESTClient
from connect.common.models import Project, OrganizationAuthorization, BillingPlan
from rest_framework import permissions


class UserAPIToken(views.APIView):

    def get(self, request, *args, **kwargs):
        project_uuid = kwargs.get("project_uuid")
        user = request.query_params.get("user")
        project = Project.objects.get(uuid=project_uuid)

        rest_client = FlowsRESTClient()
        response = rest_client.get_user_api_token(str(project.flow_organization), user)

        return JsonResponse(status=response.status_code, data=response.json())

class UserIsPaying(views.APIView):
    
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, *args, **kwargs):
        user_email = request.data.get("user_email")
        org_auth = OrganizationAuthorization.objects.filter(user__email=user_email)
        response_data = []
        
        if len(org_auth) == 0:
            return JsonResponse(status=status.HTTP_404_NOT_FOUND, data={"message": "this user doesn't have permission on any organization"})
        
        for auth in org_auth:
            current_body = {
                "org_uuid": auth.organization.uuid,
                "is_paying": auth.organization.organization_billing.plan != BillingPlan.PLAN_TRIAL,
                "project": [],
            }
            for project in auth.organization.project.all():
                current_body["project"].append(project.uuid)
            response_data.append({auth.organization.name: current_body})
        print(response_data)
        return JsonResponse(status=status.HTTP_200_OK, data=dict(orgs=response_data))
    