import logging
import uuid

import pendulum
from django.conf import settings
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg2.utils import swagger_auto_schema
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from connect.api.v1.internal.flows.flows_rest_client import FlowsRESTClient
from connect.api.v1.internal.permissions import ModuleHasPermission
from connect.api.v1.metadata import Metadata
from connect.api.v1.organization.permissions import Has2FA
from connect.api.v1.project.filters import ProjectOrgFilter
from connect.api.v1.project.permissions import (
    CanChangeProjectStatus,
    ProjectHasPermission,
)
from connect.api.v1.project.serializers import (
    ClassifierSerializer,
    CreateChannelSerializer,
    CreateClassifierSerializer,
    CreateWACChannelSerializer,
    DestroyClassifierSerializer,
    ProjectSearchSerializer,
    ProjectSerializer,
    ReleaseChannelSerializer,
    RequestPermissionProjectSerializer,
    RequestRocketPermissionSerializer,
    RetrieveClassifierSerializer,
    TemplateProjectSerializer,
    UpdateProjectStatusSerializer,
    UserAPITokenSerializer,
)
from connect.authentication.models import User
from connect.billing.models import Contact
from connect.celery import app as celery_app
from connect.common import tasks
from connect.common.models import (
    OpenedProject,
    Organization,
    OrganizationAuthorization,
    Project,
    ProjectAuthorization,
    RequestPermissionProject,
    RequestRocketPermission,
    TemplateProject,
)
from connect.internals.event_driven.producer.rabbitmq_publisher import RabbitmqPublisher
from connect.usecases.authorizations.create import CreateAuthorizationUseCase
from connect.usecases.authorizations.delete import DeleteAuthorizationUseCase
from connect.usecases.authorizations.dto import (
    CreateProjectAuthorizationDTO,
    DeleteProjectAuthorizationDTO,
)
from connect.usecases.authorizations.exceptions import (
    UserHasNoPermissionToManageProject,
)
from connect.usecases.project.update_project import UpdateProjectUseCase
from connect.utils import count_contacts, rate_limit

logger = logging.getLogger(__name__)


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
    permission_classes = [IsAuthenticated, ProjectHasPermission, Has2FA]
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

        filter = (
            Q(project_authorizations__user=self.request.user)
            & ~Q(project_authorizations__role=0)
            & Q(opened_project__user=self.request.user)
        )
        return (
            self.queryset.filter(organization__pk__in=auth)
            .filter(filter)
            .order_by("-opened_project__day")
        )

    def perform_destroy(self, instance):
        flow_organization = instance.flow_organization
        instance.delete()

        celery_app.send_task(
            "delete_project",
            args=[flow_organization, self.request.user.email],
        )

    def perform_project_authorization_destroy(self, instance, is_request_permission):
        flow_organization = instance.project.flow_organization
        project_uuid = instance.project.uuid
        if not is_request_permission:
            celery_app.send_task(
                "delete_user_permission_project",
                args=[
                    str(flow_organization),
                    str(project_uuid),
                    instance.user.email,
                    instance.role,
                ],
            )
        instance.delete()

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

        task = tasks.search_project(
            organization_id=project.organization.inteligence_organization,
            project_uuid=str(project.uuid),
            text=serializer.data.get("text"),
        )

        return Response(task)

    @action(
        detail=True,
        methods=["GET"],
        url_name="get-contact-active-detailed",
        url_path="grpc/get-contact-active-detailed/(?P<project_uuid>[^/.]+)",
    )
    def get_contact_active_detailed(self, request, project_uuid):

        before = request.query_params.get("before")
        after = request.query_params.get("after")

        if not before or not after:
            raise ValidationError(
                _("Need to pass 'before' and 'after' in query params")
            )

        before = pendulum.parse(before, strict=False).end_of("day")
        after = pendulum.parse(after, strict=False).start_of("day")
        project = Project.objects.get(uuid=project_uuid)

        contact_count = count_contacts(project, str(before), str(after))
        contacts = (
            Contact.objects.filter(project=project)
            .filter(last_seen_on__range=(after, before))
            .distinct("contact_flow_uuid")
        )

        active_contacts_info = []
        for contact in contacts:
            active_contacts_info.append(
                {"name": contact.name, "uuid": contact.contact_flow_uuid}
            )

        project_info = {
            "project_name": project.name,
            "active_contacts": contact_count,
            "contacts_info": active_contacts_info,
        }

        contact_detailed = {"projects": project_info}
        return JsonResponse(data=contact_detailed, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["DELETE"],
        url_name="destroy-user-permission",
        url_path="grpc/destroy-user-permission/(?P<project_uuid>[^/.]+)",
    )
    def destroy_user_permission(self, request, project_uuid):
        user_email = request.data.get("email")
        auth_dto = DeleteProjectAuthorizationDTO(
            user_email=user_email, project_uuid=project_uuid
        )

        usecase = DeleteAuthorizationUseCase(RabbitmqPublisher())
        usecase.delete_single_project_permission(auth_dto)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=["POST"],
        url_name="update-last-opened-on",
        url_path="update-last-opened-on/(?P<project_uuid>[^/.]+)",
    )
    def update_last_opened_on(self, request, project_uuid):
        user_email = request._user
        project = get_object_or_404(Project, uuid=project_uuid)
        user = User.objects.get(email=user_email)
        last_opened_on = OpenedProject.objects.filter(user=user, project=project)
        if last_opened_on.exists():
            last_opened_on = last_opened_on.first()
            last_opened_on.day = timezone.now()
            last_opened_on.save()
        else:
            OpenedProject.objects.create(project=project, user=user, day=timezone.now())
        return JsonResponse(
            status=status.HTTP_200_OK, data={"day": str(last_opened_on.day)}
        )

    @action(
        detail=True,
        methods=["GET"],
        url_name="list-channels",
        permission_classes=[ModuleHasPermission],
    )
    def list_channels(self, request):
        channel_type = request.query_params.get("channel_type", None)
        if not channel_type:
            raise ValidationError("Need pass the channel_type")

        task = tasks.list_channels(channel_type)
        response = dict(channels=task)
        return JsonResponse(status=status.HTTP_200_OK, data=response)

    @action(
        detail=True,
        methods=["GET"],
        url_name="realease-channel",
        serializer_class=ReleaseChannelSerializer,
        permission_classes=[ModuleHasPermission],
    )
    def release_channel(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = tasks.realease_channel(
            channel_uuid=serializer.validated_data.get("channel_uuid"),
            user=serializer.validated_data.get("user"),
        )
        return JsonResponse(status=status.HTTP_200_OK, data={"release": task})

    @action(
        detail=True,
        methods=["POST"],
        url_name="create-channel",
        serializer_class=CreateChannelSerializer,
        permission_classes=[ModuleHasPermission],
    )
    def create_channel(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            project_uuid = serializer.validated_data.get("project_uuid")
            project = Project.objects.get(uuid=project_uuid)
            rest_client = FlowsRESTClient()
            response = rest_client.create_channel(
                user=serializer.validated_data.get("user"),
                project_uuid=str(project.uuid),
                data=serializer.validated_data.get("data"),
                channeltype_code=serializer.validated_data.get("channeltype_code"),
            )
            return JsonResponse(status=response.status_code, data=response.json())

    @action(
        detail=True,
        methods=["POST"],
        url_name="create-wac-channel",
        serializer_class=CreateWACChannelSerializer,
        permission_classes=[ModuleHasPermission],
    )
    def create_wac_channel(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            project_uuid = serializer.validated_data.get("project_uuid")
            project = Project.objects.get(uuid=project_uuid)
            task = tasks.create_wac_channel(
                user=serializer.validated_data.get("user"),
                flow_organization=str(project.uuid),
                config=serializer.validated_data.get("config"),
                phone_number_id=serializer.validated_data.get("phone_number_id"),
            )

            return JsonResponse(status=status.HTTP_200_OK, data=task)

    @action(
        detail=True,
        methods=["DELETE"],
        url_name="destroy-classifier",
        serializer_class=DestroyClassifierSerializer,
        permission_classes=[ModuleHasPermission],
    )
    def destroy_classifier(self, request):
        serializer = DestroyClassifierSerializer(data=request.query_params)
        if serializer.is_valid(raise_exception=True):
            classifier_uuid = serializer.validated_data.get("uuid")
            user_email = serializer.validated_data.get("user_email")

            tasks.destroy_classifier(str(classifier_uuid), user_email)
            return JsonResponse(status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["GET"],
        url_name="retrieve-classifier",
        serializer_class=RetrieveClassifierSerializer,
        permission_classes=[ModuleHasPermission],
    )
    def retrieve_classifier(self, request):
        serializer = RetrieveClassifierSerializer(data=request.query_params)

        if serializer.is_valid(raise_exception=True):
            classifier_uuid = serializer.validated_data.get("uuid")

            task = tasks.retrieve_classifier(str(classifier_uuid))
            return JsonResponse(status=status.HTTP_200_OK, data=task)

    @action(
        detail=True,
        methods=["POST"],
        url_name="create-classifier",
        serializer_class=CreateClassifierSerializer,
        permission_classes=[ModuleHasPermission],
    )
    def create_classifier(self, request):
        request_data = request.query_params
        serializer = CreateClassifierSerializer(data=request_data)
        if serializer.is_valid(raise_exception=True):
            project_uuid = serializer.validated_data.get("project_uuid")
            project = Project.objects.get(uuid=project_uuid)
            task = tasks.create_classifier(
                project_uuid=str(project.flow_organization),
                user_email=serializer.validated_data.get("user"),
                classifier_name=serializer.validated_data.get("name"),
                access_token=serializer.validated_data.get("access_token"),
            )
            return JsonResponse(status=status.HTTP_200_OK, data=task)

    @action(
        detail=True,
        methods=["GET"],
        url_name="list-classifier",
        serializer_class=ClassifierSerializer,
        permission_classes=[ModuleHasPermission],
    )
    def list_classifier(self, request):
        serializer = ClassifierSerializer(data=request.query_params)
        if serializer.is_valid(raise_exception=True):
            project_uuid = serializer.validated_data.get("project_uuid")
            project = Project.objects.get(uuid=project_uuid)
            task = tasks.list_classifier(str(project.flow_organization))
            return JsonResponse(status=status.HTTP_200_OK, data=task)

    @action(
        detail=True,
        methods=["GET"],
        url_name="user-api-token",
    )
    def user_api_token(self, request):
        serializer = UserAPITokenSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        project_uuid = serializer.validated_data.get("project_uuid")
        user = serializer.validated_data.get("user")
        project = Project.objects.get(uuid=project_uuid)

        rest_client = FlowsRESTClient()
        response = rest_client.get_user_api_token(str(project.uuid), user)

        return JsonResponse(status=response.status_code, data=response.json())

    @action(
        detail=True,
        methods=["POST"],
        url_name="create-ticketer",
        permission_classes=[ModuleHasPermission],
    )
    def create_ticketer(self, request):
        project_uuid = request.data.get("project_uuid")
        ticketer_type = request.data.get("ticketer_type")
        name = request.data.get("name")
        config = request.data.get("config")
        project = Project.objects.get(uuid=project_uuid)
        if not settings.TESTING:
            flows_client = FlowsRESTClient()
            ticketer = flows_client.create_ticketer(
                project_uuid=str(project.flow_organization),
                ticketer_type=ticketer_type,
                name=name,
                config=config,
            )
            return JsonResponse(data=ticketer)

    @action(
        detail=True,
        methods=["GET"],
        url_name="list-flows",
        permission_classes=[ModuleHasPermission],
    )
    def list_flows(self, request, **kwargs):
        project_uuid = request.query_params.get("project_uuid")
        project = get_object_or_404(Project, uuid=project_uuid)
        task = tasks.list_project_flows(str(project.flow_organization))
        return Response(task)

    @swagger_auto_schema(
        request=UpdateProjectStatusSerializer,
        responses={200: UpdateProjectStatusSerializer},
    )
    @action(
        detail=True,
        methods=["PATCH"],
        url_name="update-status",
        permission_classes=[IsAuthenticated, CanChangeProjectStatus],
        serializer_class=UpdateProjectStatusSerializer,
    )
    def update_status(self, request, *args, **kwargs) -> Response:
        project = self.get_object()

        serializer = self.get_serializer(project, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        project.refresh_from_db()

        UpdateProjectUseCase().send_updated_project_status(project, request.user.email)

        return Response(serializer.data, status=status.HTTP_200_OK)


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

    @rate_limit(
        requests=settings.RATE_LIMIT_REQUESTS,
        window=settings.RATE_LIMIT_WINDOW,
        block_time=settings.RATE_LIMIT_BLOCK_TIME,
    )
    def create(self, request, *args, **kwargs):
        created_by: User = self.request.user
        role: int = int(self.request.data.get("role"))
        email: str = self.request.data.get("email")
        project_uuid: str = self.request.data.get("project")

        user = User.objects.filter(email=email)

        auth_dto = CreateProjectAuthorizationDTO(
            user_email=email,
            project_uuid=project_uuid,
            role=role,
            created_by_email=created_by.email,
        )

        data = {
            "created_by": created_by.email,
            "role": role,
            "email": email,
            "project": str(project_uuid),
        }

        usecase = CreateAuthorizationUseCase(RabbitmqPublisher())
        if user.exists():
            try:
                auth: ProjectAuthorization = (
                    usecase.create_authorization_for_a_single_project(auth_dto=auth_dto)
                )
            except UserHasNoPermissionToManageProject:
                return Response(
                    {
                        "status": 403,
                        "detail": "You don't have permission to manage this project",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            data.update(
                {
                    "username": auth.user.username,
                    "first_name": auth.user.first_name,
                    "last_name": auth.user.last_name,
                    "photo_user": auth.user.photo_url,
                    "is_pendent": False,
                }
            )

            return Response({"status": 200, "data": data})

        try:
            usecase.create_authorization_for_a_single_project(auth_dto=auth_dto)
        except UserHasNoPermissionToManageProject:
            return Response(
                {
                    "status": 403,
                    "detail": "You don't have permission to manage this project",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        data.update(
            {
                "username": "",
                "first_name": "",
                "last_name": "",
                "photo_user": "",
                "is_pendent": True,
            }
        )

        return Response({"status": 200, "data": data})


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


class TemplateProjectViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    queryset = TemplateProject.objects
    serializer_class = TemplateProjectSerializer
    permission_classes = [IsAuthenticated]
    metadata_class = Metadata
    lookup_field = "pk"

    def get_queryset(self, *args, **kwargs):
        if getattr(self, "swagger_fake_view", False):
            # queryset just for schema generation metadata
            return TemplateProject.objects.none()  # pragma: no cover
        auth = ProjectAuthorization.objects.exclude(role=0).filter(
            user=self.request.user
        )
        return self.queryset.filter(authorization__in=auth)

    def get_object(self):
        lookup_url_kwarg = self.lookup_field

        obj = self.get_queryset().get(
            authorization__project__uuid=self.kwargs.get(lookup_url_kwarg)
        )

        return obj

    def create(self, request, *args, **kwargs):
        data = {}
        if not request.data.get("template_type"):
            return Response(data, status=status.HTTP_400_BAD_REQUEST)

        if not settings.TESTING:
            try:
                flow_organization = tasks.create_template_project(
                    request.data.get("name"),
                    request.user.email,
                    request.data.get("timezone"),
                ).get("uuid")
            except Exception as error:
                logger.error(
                    f"Could not create template project: {error}",
                )
                data.update(
                    {"message": "Could not create template project", "status": "FAILED"}
                )
                return Response(data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            flows = {
                "uuid": uuid.uuid4(),
            }
            flow_organization = flows.get("uuid")

        organization = get_object_or_404(
            Organization, uuid=request.data.get("organization")
        )

        # Create project
        project = Project.objects.create(
            date_format=request.data.get("date_format"),
            name=request.data.get("name"),
            organization=organization,
            timezone=str(request.data.get("timezone")),
            flow_organization=flow_organization,
            is_template=True,
            created_by=request.user,
            template_type=request.data.get("template_type"),
        )

        if len(Project.objects.filter(created_by=project.created_by)) == 1:
            data = dict(
                send_request_flow=settings.SEND_REQUEST_FLOW_PRODUCT,
                flow_uuid=settings.FLOW_PRODUCT_UUID,
                token_authorization=settings.TOKEN_AUTHORIZATION_FLOW_PRODUCT,
            )
            project.created_by.send_request_flow_user_info(data)

        project_data = {
            "project": project,
        }

        TemplateProjectSerializer().create(project_data, request)

        serializer = ProjectSerializer(project, context={"request": request})
        data.update({"message": "", "status": "SUCCESS"})
        data.update(serializer.data)
        return Response(data, status=status.HTTP_201_CREATED)
