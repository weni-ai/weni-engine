from rest_framework import mixins
from rest_framework.viewsets import GenericViewSet

from connect.common.models import Project
from connect.api.v1.project.serializers import ProjectSerializer
from connect.api.v1.internal.permissions import ModuleHasPermission


class AIGetProjectViewSet(mixins.RetrieveModelMixin, GenericViewSet):
    queryset = Project.objects
    serializer_class = ProjectSerializer
    lookup_field = "uuid"
    permission_classes = [ModuleHasPermission]

    def get_queryset(self, **kwargs):
        if getattr(self, "swagger_fake_view", False):
            return Project.objects.none()  # pragma: no cover

        return super().get_queryset()
