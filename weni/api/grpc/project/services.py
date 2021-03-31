from django_grpc_framework import generics

from weni import utils
from weni.api.grpc.project.serializers import ClassifierRequestSerializer
from weni.common.models import Project
from weni.protos.weni.project_pb2 import ClassifierResponse


class ProjectService(generics.GenericService):
    def Classifier(self, request, context):
        serializer = ClassifierRequestSerializer(message=request)

        if serializer.is_valid(raise_exception=True):
            project_uuid = serializer.validated_data.get("project_uuid")

            project = Project.objects.get(uuid=project_uuid)

            grpc_instance = utils.get_grpc_types().get("flow")
            response = grpc_instance.get_classifiers(
                project_uuid=str(project.flow_organization),
                classifier_type="bothub",
            )

            for i in response:
                yield ClassifierResponse(
                    authorization_uuid=i.get("authorization_uuid"),
                    classifier_type=i.get("classifier_type"),
                    name=i.get("name"),
                )
