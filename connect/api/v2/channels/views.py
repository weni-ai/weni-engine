import logging

from django.http import JsonResponse
from rest_framework import views, status
from rest_framework.exceptions import ValidationError

from connect.api.v1.internal.permissions import ModuleHasPermission
from connect.api.v1.internal.flows.flows_rest_client import FlowsRESTClient
from connect.api.v2.channels.serializers import ReleaseChannelSerializer, CreateChannelSerializer, CreateWACChannelSerializer
from connect.common.models import Project

logger = logging.getLogger(__name__)


class ChannelsAPIView(views.APIView):
    permission_classes = [ModuleHasPermission]

    def delete(self, request, *args, **kwargs):
        serializer = ReleaseChannelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        channel_uuid = serializer.validated_data.get("channel_uuid")
        user = serializer.validated_data.get("user")

        flow_instance = FlowsRESTClient()
        flow_instance.release_channel(
            channel_uuid=channel_uuid,
            user=user,
        )

        return JsonResponse(status=status.HTTP_200_OK, data={"release": True})

    def post(self, request, *args, **kwargs):
        data = request.data
        data.update({"project_uuid": kwargs.get("project_uuid")})
        logger.info(f"[ * ] {data}")
        serializer = CreateChannelSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        project_uuid = serializer.validated_data.get("project_uuid")
        project = Project.objects.get(uuid=project_uuid)
        logger.info(f"project its found {project.name}")

        flows_instance = FlowsRESTClient()
        response = flows_instance.create_channel(
            user=serializer.validated_data.get("user"),
            project_uuid=str(project.flow_organization),
            data=serializer.validated_data.get("data"),
            channeltype_code=serializer.validated_data.get("channeltype_code"),
        )
        logger.info(f"status = {response.status_code}")
        if response.status_code != status.HTTP_200_OK:
            return JsonResponse(status=response.status_code, data={"message": response.text})
        return JsonResponse(status=response.status_code, data=response.json())


class ListChannelsAPIView(views.APIView):
    permission_classes = [ModuleHasPermission]

    def get(self, request):
        channel_type = request.query_params.get("channel_type", None)
        if not channel_type:
            raise ValidationError("Need pass the channel_type")
        flow_instance = FlowsRESTClient()
        response = flow_instance.list_channel(channel_type=channel_type)
        channels = []
        for channel in response:
            org = channel.get("org")
            project = Project.objects.filter(flow_organization=org)
            if project:
                project = project.first()
                channel_data = dict(
                    uuid=str(channel.get("uuid")),
                    name=channel.get("name"),
                    config=channel.get("config"),
                    address=channel.get("address"),
                    project_uuid=str(project.uuid),
                    is_active=channel.get("is_active")
                )
                channels.append(channel_data)
        return JsonResponse(data={"channels": channels}, status=status.HTTP_200_OK)


class CreateWACChannelAPIView(views.APIView):
    permission_classes = [ModuleHasPermission]

    def post(self, request):
        serializer = CreateWACChannelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        project_uuid = serializer.validated_data.get("project_uuid")
        project = Project.objects.get(uuid=project_uuid)

        flow_instance = FlowsRESTClient()
        project_data = flow_instance.create_wac_channel(
            user=serializer.validated_data.get("user"),
            flow_organization=str(project.flow_organization),
            config=serializer.validated_data.get("config"),
            phone_number_id=serializer.validated_data.get("phone_number_id")
        )

        return JsonResponse(status=status.HTTP_200_OK, data=project_data)
