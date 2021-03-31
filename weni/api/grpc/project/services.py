from django_grpc_framework import mixins, generics

from weni.api.grpc.project.serializers import ClassifierRequestSerializer


class ProjectService(mixins.ListModelMixin, generics.GenericService):
    def Classifier(self, request, context):

        serializer = ClassifierRequestSerializer(message=request)
        # if serializer.is_valid():
        #     org_uuid = serializer.validated_data["org_uuid"]
        #     before = serializer.validated_data["before"]
        #     after = serializer.validated_data["after"]
        #     total_count = Query.total(org_uuid, before, after)
        #     return BillingResponse(active_contacts=total_count)