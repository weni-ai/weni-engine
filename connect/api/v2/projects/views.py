from rest_framework import mixins, status
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from connect.common.models import (
    Project,
    OpenedProject,
)
from connect.api.v2.projects.serializers import (
    ProjectSerializer,
)

from django.utils import timezone


class ProjectViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet
):
    queryset = Project.objects
    serializer_class = ProjectSerializer
    lookup_field = "uuid"
    permission_classes = [IsAuthenticated]

    def get_queryset(self, **kwargs):
        if getattr(self, "swagger_fake_view", False):
            return Project.objects.none()  # pragma: no cover

        return super().get_queryset().filter(organization__uuid=self.kwargs["organization_uuid"])

    @action(
        detail=True,
        methods=["GET"],
        url_name="project-search",
    )
    def project_search(self, request, **kwargs):
        # text = serializer.data.get("text")

        text = request.query_params.get("text")

        instance = self.get_object()
        self.check_object_permissions(self.request, instance)
        response = instance.project_search(text)
        return Response(response)

    @action(
        detail=True,
        methods=["POST"],  # change to patch
        url_name="update-last-opened-on"
    )
    def update_last_opened_on(self, request, **kwargs):
        instance = self.get_object()
        user = request.user

        last_opened_on = OpenedProject.objects.filter(user=user, project=instance)

        if last_opened_on.exists():
            last_opened_on = last_opened_on.first()
            last_opened_on.day = timezone.now()  # TODO change to pendulum
            last_opened_on.save()
        else:
            OpenedProject.objects.create(project=instance, user=user, day=timezone.now())
        return Response(data={"day": str(last_opened_on.day)}, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        request.data.update(
            {
                "organization": kwargs.get("organization_uuid")
            }
        )
        return super(ProjectViewSet, self).create(request, *args, **kwargs)

    def perform_destroy(self, instance):
        user_email = self.request.user.email
        instance.perform_destroy_flows_project(user_email)

        instance.delete()
