from rest_framework import mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import GenericViewSet

from weni.api.v1.metadata import Metadata
from weni.api.v1.project.filters import ProjectOrgFilter
from weni.api.v1.project.permissions import ProjectHasPermission
from weni.api.v1.project.serializers import ProjectSeralizer
from weni.common.models import OrganizationAuthorization, Project


class ProjectViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    queryset = Project.objects.all()
    serializer_class = ProjectSeralizer
    permission_classes = [IsAuthenticated, ProjectHasPermission]
    filter_class = ProjectOrgFilter
    lookup_field = "uuid"
    metadata_class = Metadata

    def get_queryset(self, *args, **kwargs):
        if getattr(self, "swagger_fake_view", False):
            # queryset just for schema generation metadata
            return Project.objects.none()
        auth = (
            OrganizationAuthorization.objects.exclude(role=0)
            .filter(user=self.request.user)
            .values("organization")
        )
        return self.queryset.filter(organization__pk__in=auth)
