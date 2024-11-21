from rest_framework import mixins, status
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from connect.api.v1.organization.permissions import Has2FA
from connect.api.v1.project.permissions import ProjectHasPermission

from connect.common.models import Project, OpenedProject, TypeProject
from connect.api.v2.projects.serializers import (
    ProjectSerializer,
    ProjectUpdateSerializer,
    ProjectListAuthorizationSerializer,
    OpenedProjectSerializer,
)

from django.utils import timezone
from connect.api.v2.paginations import (
    CustomCursorPagination,
    OpenedProjectCustomCursorPagination,
)


class ProjectViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    queryset = Project.objects
    serializer_class = ProjectSerializer
    lookup_field = "uuid"
    permission_classes = [IsAuthenticated, ProjectHasPermission, Has2FA]
    pagination_class = CustomCursorPagination

    def get_queryset(self, **kwargs):
        if getattr(self, "swagger_fake_view", False):
            return Project.objects.none()  # pragma: no cover

        if self.kwargs.get("organization_uuid"):
            return (
                super()
                .get_queryset()
                .filter(organization__uuid=self.kwargs["organization_uuid"])
            )
        return super().get_queryset()

    def get_ordering(self):
        valid_fields = (org_fields.name for org_fields in Project._meta.get_fields())
        ordering = []
        for param in self.request.query_params.getlist("ordering"):
            if param.startswith("-"):
                field = param[1:]
            else:
                field = param
            if field in valid_fields:
                ordering.append(param)
        return ordering or ["created_at"]

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
        url_name="update-last-opened-on",
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
            OpenedProject.objects.create(
                project=instance, user=user, day=timezone.now()
            )
        return Response(
            data={"day": str(last_opened_on.day)}, status=status.HTTP_200_OK
        )

    def update(self, request, *args, **kwargs):
        self.serializer_class = ProjectUpdateSerializer
        return super(ProjectViewSet, self).update(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        request.data.update(
            {"organization": kwargs.get("organization_uuid"), "project_view": True}
        )
        return super(ProjectViewSet, self).create(request, *args, **kwargs)

    def perform_destroy(self, instance):
        user_email = self.request.user.email
        instance.perform_destroy_flows_project(user_email)

        instance.delete()

    @action(detail=True, methods=["POST"], url_name="set-type")
    def set_type(self, request, **kwargs):
        instance = self.get_object()
        try:
            project_type = request.data.get("project_type")

            if project_type not in [choice[0] for choice in TypeProject.choices]:
                choices_text = []
                for value, label in TypeProject.choices:
                    choices_text.append(f"{value} ({label.title()})")
                return Response(
                    {"detail": f"Invalid type. Choices are: {', '.join(choices_text)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            instance.project_type = project_type
            instance.save(update_fields=["project_type"])

            return Response(
                {"project_type": instance.project_type}, status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ProjectAuthorizationViewSet(mixins.RetrieveModelMixin, GenericViewSet):
    queryset = Project.objects
    serializer_class = ProjectListAuthorizationSerializer
    permission_classes = [IsAuthenticated, ProjectHasPermission, Has2FA]
    lookup_field = "uuid"


class OpenedProjectViewSet(mixins.ListModelMixin, GenericViewSet):
    queryset = OpenedProject.objects.select_related("project", "user")
    serializer_class = OpenedProjectSerializer
    permission_classes = [IsAuthenticated, ProjectHasPermission, Has2FA]
    lookup_field = "uuid"
    pagination_class = OpenedProjectCustomCursorPagination

    def get_queryset(self, **kwargs):
        if getattr(self, "swagger_fake_view", False):
            return OpenedProject.objects.none()  # pragma: no cover

        organization__uuid = self.kwargs["organization_uuid"]
        projects = Project.objects.filter(organization__uuid=organization__uuid)
        opened_projects = super().get_queryset().filter(project__in=projects)
        return opened_projects

    def get_ordering(self):
        valid_fields = (
            opened_project.name for opened_project in OpenedProject._meta.get_fields()
        )
        ordering = ["project"]
        for param in self.request.query_params.getlist("ordering"):
            if param.startswith("-"):
                field = param[1:]
            else:
                field = param
            if field in valid_fields:
                ordering.append(param)
        return ordering or ["project", "day"]
