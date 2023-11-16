from rest_framework import status, mixins
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from django.contrib.auth import get_user_model

from .serializers import RecentActivitySerializer, ListRecentActivitySerializer
from connect.api.v2.recent_activity.paginations import CustomCursorPagination
from connect.api.v1.internal.permissions import ModuleHasPermission
from connect.common.models import Project, RecentActivity

User = get_user_model()


class RecentActivityViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, GenericViewSet):
    queryset = RecentActivity.objects.all()
    # serializer_class = RecentActivitySerializer
    pagination_class = CustomCursorPagination

    def get_permissions(self):
        if self.action == "create":
            self.permission_classes = [ModuleHasPermission]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == "list":
            return ListRecentActivitySerializer
        return RecentActivitySerializer

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_201_CREATED)

    def list(self, request):

        project_uuid = request.query_params.get("project")
        try:
            project = Project.objects.get(uuid=project_uuid)
        except Project.DoesNotExist:
            return Response({"message": "Project does not exist."}, status=status.HTTP_404_NOT_FOUND)

        if not project.project_authorizations.filter(user__email=request.user.email).exists():
            return Response({"message": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        queryset = RecentActivity.objects.select_related("user").filter(project__uuid=project_uuid).order_by("-created_on")
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)

        return self.get_paginated_response(serializer.data)
