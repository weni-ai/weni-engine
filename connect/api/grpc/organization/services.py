from connect.common.models import Organization
from weni.protobuf.connect.organization_pb2 import OrganizationResponse
from django_grpc_framework import generics


class OrganizationService(generics.GenericService):
    def Retrieve(self, request, context):

        organization_uuid = request.uuid
        organization = Organization.objects.get(uuid=organization_uuid)

        return OrganizationResponse(
            uuid=str(organization.uuid),
            name=organization.name,
            description=organization.description,
            inteligence_organization=organization.inteligence_organization,
            extra_integration=organization.extra_integration,
            is_suspended=organization.is_suspended,
        )
