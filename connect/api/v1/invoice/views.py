from botocore.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import GenericViewSet
from rest_framework.decorators import action

from connect.api.v1.invoice.filters import InvoiceFilter
from connect.api.v1.invoice.serializers import InvoiceSerializer
from connect.api.v1.metadata import Metadata
from connect.common.models import Invoice, Organization
from django.utils.translation import ugettext_lazy as _


class InvoiceViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    queryset = Invoice.objects
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]
    filter_class = InvoiceFilter
    filter_backends = [OrderingFilter, SearchFilter, DjangoFilterBackend]
    lookup_field = "pk"
    metadata_class = Metadata

    @action(
        detail=True,
        methods=["GET"],
        url_name="invoice-data",
        url_path="invoice-data/(?P<organization_uuid>[^/.]+)",
    )
    def invoice_data(
            self, request, organization_uuid
    ):
        organization = get_object_or_404(Organization, uuid=organization_uuid)

        self.check_object_permissions(self.request, organization)

        after = str(request.query_params.get('after') + "00:01")
        before = str(request.query_params.get('before') + "23:59")

        if (not before) or (not after):
            raise ValidationError(
                _("Need to pass 'before' and 'after' in query params")
            )

        flow_instance = utils.get_grpc_types().get("flow")