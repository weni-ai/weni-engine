from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django.contrib.auth import get_user_model

from connect.api.v1.internal.permissions import ModuleHasPermission
from connect.common.models import Project, RecentActivity

User = get_user_model()


class RecentActivityAPIView(views.APIView):

    permission_classes = [ModuleHasPermission]

    def post(self, request):
        try:
            user = User.objects.get(email=request.data.get("user"))
        except User.DoesNotExist:
            return Response(
                status=status.HTTP_200_OK,
                data={"message": "The User does not exist. Action ignored"},
            )

        intelligence_id = request.data.get("intelligence_id", None)
        if intelligence_id:
            return Response(
                status=status.HTTP_200_OK,
                data={
                    "message": "The Intelligence ID is not supported. Action ignored"
                },
            )

        action = request.data.get("action")
        entity = request.data.get("entity")
        entity_name = request.data.get("entity_name")
        flow_organization = request.data.get("flow_organization", None)
        project_uuid = request.data.get("project_uuid", None)

        if flow_organization:
            project = Project.objects.filter(flow_organization=flow_organization)
        else:
            project = Project.objects.filter(uuid=project_uuid)

        if len(project) > 0:
            project = project.first()
        else:
            return Response(
                status=status.HTTP_404_NOT_FOUND,
                data=dict(message="error: Project not found"),
            )

        RecentActivity.objects.create(
            action=action,
            entity=entity,
            user=user,
            project=project,
            entity_name=entity_name,
        )

        return Response(status=status.HTTP_200_OK)


class RecentActivityListAPIView(views.APIView):
    def get(self, request):

        project_uuid = request.query_params.get("project")
        project = Project.objects.get(uuid=project_uuid)

        if not project.project_authorizations.filter(
            user__email=request.user.email
        ).exists():
            raise PermissionDenied()

        recent_activities = RecentActivity.objects.filter(
            project__uuid=project_uuid
        ).order_by("-created_on")
        data = [recent_activity.to_json for recent_activity in recent_activities]
        return Response(status=status.HTTP_200_OK, data=data)
