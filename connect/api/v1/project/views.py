from django.utils.translation import ugettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from connect.api.v1.metadata import Metadata
from connect.api.v1.project.filters import ProjectOrgFilter
from connect.api.v1.project.permissions import ProjectHasPermission
from connect.api.v1.project.serializers import (
    ProjectSerializer,
    ProjectSearchSerializer,
    RequestRocketPermissionSerializer,
    RequestPermissionProjectSerializer,
)
from connect.celery import app as celery_app
from connect.common.models import (
    OrganizationAuthorization,
    Project,
    RequestPermissionProject,
    RequestRocketPermission,
)

from connect.middleware import ExternalAuthentication
from rest_framework.exceptions import ValidationError
from connect.common import tasks
from django.http import JsonResponse
from django.db.models import Q


class ProjectViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated, ProjectHasPermission]
    filter_class = ProjectOrgFilter
    filter_backends = [OrderingFilter, SearchFilter, DjangoFilterBackend]
    lookup_field = "uuid"
    metadata_class = Metadata

    def get_queryset(self, *args, **kwargs):
        if getattr(self, "swagger_fake_view", False):
            # queryset just for schema generation metadata
            return Project.objects.none()  # pragma: no cover
        auth = (
            OrganizationAuthorization.objects.exclude(role=0)
            .filter(user=self.request.user)
            .values("organization")
        )

        filter = Q(project_authorizations__user=self.request.user) & ~Q(
            project_authorizations__role=0
        )

        return self.queryset.filter(organization__pk__in=auth).filter(filter)

    def perform_destroy(self, instance):
        flow_organization = instance.flow_organization
        instance.delete()

        celery_app.send_task(
            "delete_project",
            args=[flow_organization, self.request.user.email],
        )

    @action(
        detail=True,
        methods=["GET"],
        url_name="project-search",
        serializer_class=ProjectSearchSerializer,
    )
    def project_search(self, request, **kwargs):  # pragma: no cover
        serializer = ProjectSearchSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        project = Project.objects.get(pk=serializer.data.get("project_uuid"))

        user_authorization = project.organization.get_user_authorization(
            self.request.user
        )
        if not user_authorization.can_contribute:
            raise PermissionDenied(
                _("You can't contribute in this organization")
            )  # pragma: no cover

        task = celery_app.send_task(  # pragma: no cover
            name="search_project",
            args=[
                project.organization.inteligence_organization,
                str(project.flow_organization),
                serializer.data.get("text"),
            ],
        )
        task.wait()  # pragma: no cover

        return Response(task.result)

    @action(
        detail=True,
        methods=["GET"],
        url_name="get-contact-active-detailed",
        url_path="grpc/get-contact-active-detailed/(?P<project_uuid>[^/.]+)",
        authentication_classes=[ExternalAuthentication],
        permission_classes=[AllowAny],
    )
    def get_contact_active_detailed(self, request, project_uuid):

        before = str(request.query_params.get("before") + " 00:00")
        after = str(request.query_params.get("after") + " 00:00")

        if not before or not after:
            raise ValidationError(
                _("Need to pass 'before' and 'after' in query params")
            )
        task = tasks.get_contacts_detailed.delay(str(project_uuid), before, after)
        task.wait()
        contact_detailed = {"projects": task.result}
        return JsonResponse(data=contact_detailed, status=status.HTTP_200_OK)


class RequestPermissionProjectViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    queryset = RequestPermissionProject.objects.all()
    serializer_class = RequestPermissionProjectSerializer
    permission_classes = [IsAuthenticated]
    metadata_class = Metadata

    def create(request, *args, **kwargs):
        created_by = request.request.user
        role = request.request.data.get('role')
        email = request.request.data.get('email')
        project_uuid = request.request.data.get('project')
        project = Project.objects.filter(uuid=project_uuid)
        if len(project) == 0:
            return Response({"status": 404, "message": f"Project {project_uuid} not found"})
        project = project.first()

        request_permission = RequestPermissionProject.objects.filter(email=email, project=project)
        project_auth = project.project_authorizations.filter(user__email=email)

        if request_permission.exists():
            request_permission = request_permission.first()
            request_permission.role = role
            request_permission.save()
        elif project_auth.exists():
            project_auth = project_auth.first()
            project_auth.role = role
            project_auth.save()
        else:
            RequestPermissionProject.objects.create(created_by=created_by, email=email, role=role, project=project)
        
        return Response({"status": 200, "data": {"created_by": created_by.email, "role": role, "email": email, "project": project_uuid}})


class RequestPermissionRocketViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    queryset = RequestRocketPermission.objects.all()
    serializer_class = RequestRocketPermissionSerializer
    permission_classes = [IsAuthenticated]
    metadata_class = Metadata
    lookup_field = "pk"
