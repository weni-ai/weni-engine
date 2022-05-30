from django.shortcuts import get_object_or_404
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
    ReleaseChannelSerializer,
    DestroyClassifierSerializer,
    CreateChannelSerializer,
    RetrieveClassifierSerializer,
    CreateClassifierSerializer,
    ClassifierSerializer,
)
from connect.celery import app as celery_app
from connect.common.models import (
    OrganizationAuthorization,
    Project,
    RequestPermissionProject,
    RequestRocketPermission,
    ProjectAuthorization,
    RocketAuthorization
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

    def perform_project_authorization_destroy(self, instance, is_request_permission):
        flow_organization = instance.project.flow_organization
        if not is_request_permission:
            celery_app.send_task(
                "delete_user_permission_project",
                args=[flow_organization, instance.user.email, instance.role],
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

    @action(
        detail=True,
        methods=["DELETE"],
        url_name="destroy-user-permission",
        url_path="grpc/destroy-user-permission/(?P<project_uuid>[^/.]+)",
        authentication_classes=[ExternalAuthentication],
        permission_classes=[AllowAny],
    )
    def destroy_user_permission(self, request, project_uuid):
        user_email = request.data.get('email')
        project = get_object_or_404(Project, uuid=project_uuid)

        project_permission = project.project_authorizations.filter(
            user__email=user_email)
        request_permission = project.requestpermissionproject_set.filter(
            email=user_email)

        if request_permission.exists():
            self.perform_project_authorization_destroy(request_permission.first(), True)
            return Response(status=status.HTTP_204_NO_CONTENT)

        elif project_permission.exists():
            self.perform_project_authorization_destroy(project_permission.first(), False)
            return Response(status=status.HTTP_204_NO_CONTENT)

        return Response(status=status.HTTP_404_NOT_FOUND)

    @action(
        detail=True,
        methods=["GET"],
        url_name="list-channel",
        authentication_classes=[ExternalAuthentication],
        permission_classes=[AllowAny],
    )
    def list_channel(self, request):
        channel_type = request.data.get('channel_type', None)
        if not channel_type:
            return JsonResponse(status=status.HTTP_400_BAD_REQUEST, data={"message": "Need pass the channel_type"})

        response = []

        for project in Project.objects.all():
            task = tasks.list_channels.delay(
                project_uuid=str(project.flow_organization),
                channel_type=channel_type,
            )
            task.wait()
            response.append(dict(project_uuid=str(project.uuid), channels=task.result))

        return JsonResponse(status=status.HTTP_200_OK, data={"data": response})

    @action(
        detail=True,
        methods=["GET"],
        url_name="realease-channel",
        serializer_class=ReleaseChannelSerializer,
        authentication_classes=[ExternalAuthentication],
        permission_classes=[AllowAny],
    )
    def release_channel(self, request):
        serializer = ReleaseChannelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = tasks.realease_channel.delay(
            channel_uuid=serializer.validated_data.get("channel_uuid"),
            user=serializer.validated_data.get("user"),
        )
        task.wait()
        return JsonResponse(status=status.HTTP_200_OK, data={"release": task.result})

    @action(
        detail=True,
        methods=["POST"],
        url_name='create-channel',
        serializer_class=CreateChannelSerializer,
        authentication_classes=[ExternalAuthentication],
        permission_classes=[AllowAny],
    )
    def create_channel(self, request):
        serializer = CreateChannelSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            project_uuid = serializer.validated_data.get("project_uuid")
            project = Project.objects.get(uuid=project_uuid)

            task = tasks.create_channel.delay(
                user=serializer.validated_data.get("user"),
                project_uuid=str(project.flow_organization),
                data=serializer.validated_data.get("data"),
                channeltype_code=serializer.validated_data.get("channeltype_code"),
            )
            task.wait()
            response = task.result

            return JsonResponse(status=status.HTTP_200_OK, data=task.result)

    @action(
        detail=True,
        methods=["DELETE"],
        url_name='destroy-classifier',
        serializer_class=DestroyClassifierSerializer,
        authentication_classes=[ExternalAuthentication],
        permission_classes=[AllowAny],
    )
    def destroy_classifier(self, request):
        serializer = DestroyClassifierSerializer(data=request.query_params)
        if serializer.is_valid(raise_exception=True):
            classifier_uuid = serializer.validated_data.get("uuid")
            user_email = serializer.validated_data.get("user_email")

            task = tasks.delete_classifier.delay(
                classifier_uuid=str(classifier_uuid),
                user_email=user_email,
            )
            task.wait()

            return JsonResponse(status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["GET"],
        url_name='retrieve-classifier',
        serializer_class=RetrieveClassifierSerializer,
        authentication_classes=[ExternalAuthentication],
        permission_classes=[AllowAny],
    )
    def retrieve_classifier(self, request):
        serializer = RetrieveClassifierSerializer(data=request.query_params)

        if serializer.is_valid(raise_exception=True):
            classifier_uuid = serializer.validated_data.get("uuid")

            task = tasks.retrieve_classifier.delay(classifier_uuid=classifier_uuid)
            task.wait()
            response = task.result

            data = {
                "authorization_uuid": response.get("access_token"),
                "classifier_type": response.get("classifier_type"),
                "name": response.get("name"),
                "is_active": response.get("is_active"),
                "uuid": response.get("uuid"),
            }
            return JsonResponse(status=status.HTTP_200_OK, data=data)

    @action(
        detail=True,
        methods=["POST"],
        url_name='create-classifier',
        serializer_class=CreateClassifierSerializer,
        authentication_classes=[ExternalAuthentication],
        permission_classes=[AllowAny],
    )
    def create_classifier(self, request):
        request_data = request.query_params
        serializer = CreateClassifierSerializer(data=request_data)
        if serializer.is_valid(raise_exception=True):
            project_uuid = serializer.validated_data.get("project_uuid")
            project = Project.objects.get(uuid=project_uuid)

            task = tasks.create_classifier.delay(
                project_uuid=str(project.flow_organization),
                user_email=serializer.validated_data.get("user"),
                classifier_name=serializer.validated_data.get("name"),
                access_token=serializer.validated_data.get("access_token")
            )
            task.wait()
            response = task.result

            created_classifier = {
                "authorization_uuid": response.get("access_token"),
                "classifier_type": response.get("classifier_type"),
                "name": response.get("name"),
                "is_active": response.get("is_active"),
                "uuid": response.get("uuid"),
            }

            return JsonResponse(status=status.HTTP_200_OK, data=created_classifier)

    @action(
        detail=True,
        methods=["GET"],
        url_name='list-classifier',
        serializer_class=ClassifierSerializer,
        authentication_classes=[ExternalAuthentication],
        permission_classes=[AllowAny],
    )
    def list_classifier(self, request):
        serializer = ClassifierSerializer(data=request.query_params)

        if serializer.is_valid(raise_exception=True):
            project_uuid = serializer.validated_data.get("project_uuid")
            project = Project.objects.get(uuid=project_uuid)

            task = tasks.list_classifiers.delay(project_uuid=str(project.flow_organization))
            task.wait()
            response = task.result
            classifiers = {"data": []}
            for i in response:
                classifiers["data"].append({
                    "authorization_uuid": i.get("authorization_uuid"),
                    "classifier_type": i.get("classifier_type"),
                    "name": i.get("name"),
                    "is_active": i.get("is_active"),
                    "uuid": i.get("uuid"),
                })
            return JsonResponse(status=status.HTTP_200_OK, data=classifiers)


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
        rocket_role = request.request.data.get('rocket_authorization')
        project = Project.objects.filter(uuid=project_uuid)

        if len([item for item in ProjectAuthorization.ROLE_CHOICES if item[0] == role]) == 0:
            return Response({"status": 422, "message": f"{role} is not a valid role!"})
        if len(project) == 0:
            return Response({"status": 404, "message": f"Project {project_uuid} not found!"})
        project = project.first()

        if len([item for item in RocketAuthorization.ROLE_CHOICES if item[0] == rocket_role]) == 0 and rocket_role:
            return Response({"status": 422, "message": f"{rocket_role} is not a valid rocket role!"})

        request_permission = RequestPermissionProject.objects.filter(email=email, project=project)
        project_auth = project.project_authorizations.filter(user__email=email)

        request_rocket_authorization = RequestRocketPermission.objects.filter(email=email, project=project)
        rocket_authorization = None

        user_name = ''
        first_name = ''
        last_name = ''
        photo = ''
        is_pendent = False

        if request_permission.exists():
            request_permission = request_permission.first()
            is_pendent = True
            request_permission.role = role
            request_permission.save()
        elif project_auth.exists():
            project_auth = project_auth.first()
            rocket_authorization = project_auth.rocket_authorization
            user_name = project_auth.user.username
            first_name = project_auth.user.first_name
            last_name = project_auth.user.last_name
            photo = project_auth.user.photo_url
            project_auth.role = role
            project_auth.save()
        else:
            RequestPermissionProject.objects.create(created_by=created_by, email=email, role=role, project=project)
            is_pendent = RequestPermissionProject.objects.filter(email=email, project=project).exists()

        if request_rocket_authorization.exists():
            request_rocket_authorization = request_rocket_authorization.first()
            request_rocket_authorization.role = rocket_role
            request_rocket_authorization.save()
        elif not (rocket_authorization is None):
            rocket_authorization.role = rocket_role
            rocket_authorization.save()
        elif rocket_role:
            RequestRocketPermission.objects.create(email=email, role=rocket_role, project=project, created_by=created_by)

        return Response({"status": 200, "data": {"created_by": created_by.email, "role": role, "rocket_authorization": rocket_role, "email": email, "project": project_uuid, "username": user_name, "first_name": first_name, "last_name": last_name, "photo_user": photo, "is_pendent": is_pendent}})


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
