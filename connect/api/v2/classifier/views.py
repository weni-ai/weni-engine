from rest_framework import views, status

from django.conf import settings
from django.http import JsonResponse


from connect.api.v1.internal.permissions import ModuleHasPermission
from connect.api.v1.internal.flows.flows_rest_client import FlowsRESTClient
from connect.api.v2.classifier.serializers import (
    CreateClassifierSerializer,
    ListClassifierSerializer,
    RetrieveClassifierSerializer,
    DeleteClassifierSerializer,
)
from connect.common.models import Project


class CreateClassifierAPIView(views.APIView):
    permission_classes = [ModuleHasPermission]

    def post(self, request):
        request_data = request.query_params
        serializer = CreateClassifierSerializer(data=request_data)
        serializer.is_valid(raise_exception=True)

        project_uuid = serializer.validated_data.get("project_uuid")
        user_email = serializer.validated_data.get("user")
        classifier_name = serializer.validated_data.get("name")
        access_token = serializer.validated_data.get("access_token")
        project = Project.objects.get(uuid=project_uuid)

        flow_instance = FlowsRESTClient()
        classifier_data = flow_instance.create_classifier(
            project_uuid=str(project.uuid),
            user_email=user_email,
            classifier_type="bothub",
            classifier_name=classifier_name,
            access_token=access_token,
        ).get("data", {})
        return JsonResponse(status=status.HTTP_200_OK, data=classifier_data)


class ListClassifierAPIView(views.APIView):
    permission_classes = [ModuleHasPermission]

    def get(self, request):
        request_data = request.query_params
        serializer = ListClassifierSerializer(data=request_data)
        serializer.is_valid(raise_exception=True)

        project_uuid = serializer.validated_data.get("project_uuid")
        project = Project.objects.get(uuid=project_uuid)

        classifier_data = {"data": []}

        flow_instance = FlowsRESTClient()

        response = flow_instance.get_classifiers(
            project_uuid=str(project.uuid), classifier_type="bothub", is_active=True
        )

        for i in response:
            authorization = (
                i.get("access_token")
                if settings.USE_FLOW_REST
                else i.get("authorization_uuid")
            )
            classifier_data["data"].append(
                {
                    "authorization_uuid": authorization,
                    "classifier_type": i.get("classifier_type"),
                    "name": i.get("name"),
                    "is_active": i.get("is_active"),
                    "uuid": i.get("uuid"),
                }
            )
        return JsonResponse(status=status.HTTP_200_OK, data=classifier_data)


class RetrieveClassfierAPIView(views.APIView):

    permission_classes = [ModuleHasPermission]

    def get(self, request):
        serializer = RetrieveClassifierSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        classifier_uuid = serializer.validated_data.get("uuid")
        flow_instance = FlowsRESTClient()
        response = flow_instance.get_classifiers(classifier_uuid=str(classifier_uuid))
        classifier_data = dict(
            authorization_uuid=response.get("access_token"),
            classifier_type=response.get("classifier_type"),
            name=response.get("name"),
            is_active=response.get("is_active"),
            uuid=response.get("uuid"),
        )
        return JsonResponse(status=status.HTTP_200_OK, data=classifier_data)


class DeleteClassifierAPIView(views.APIView):
    permission_classes = [ModuleHasPermission]

    def delete(self, request):
        serializer = DeleteClassifierSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        classifier_uuid = serializer.validated_data.get("uuid")
        user_email = serializer.validated_data.get("user_email")

        FlowsRESTClient().delete_classifier(
            classifier_uuid=classifier_uuid, user_email=user_email
        )

        return JsonResponse(status=status.HTTP_200_OK)
