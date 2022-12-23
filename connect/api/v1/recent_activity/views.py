from rest_framework import views, status
from rest_framework.response import Response

from django.contrib.auth import get_user_model

from connect.api.v1.internal.permissions import ModuleHasPermission
from connect.common.models import Project, RecentActivity

User = get_user_model()


class RecentActivityAPIView(views.APIView):
    permission_classes = [ModuleHasPermission]

    def post(self, request):
        if request.data.get("flow_organization"):
            project = Project.objects.filter(flow_organization=request.data.get("flow_organization"))
        else:
            project = Project.objects.filter(uuid=request.data.get("project_uuid"))

        if len(project) > 0:
            project = project.first()
        else:
            return Response(status=status.HTTP_404_NOT_FOUND, data=dict(message="error: Project not found"))

        action = request.data.get("action")
        entity = request.data.get("entity")
        entity_name = request.data.get("entity_name")
        user = User.objects.get(email=request.data.get("user"))
        RecentActivity.objects.create(
            action=action,
            entity=entity,
            user=user,
            project=project,
            entity_name=entity_name
        )
        return Response(status=status.HTTP_200_OK)
