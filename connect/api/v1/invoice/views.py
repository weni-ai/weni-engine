from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import GenericViewSet
from rest_framework.decorators import action

from django.utils import timezone

from connect.api.v1.invoice.filters import InvoiceFilter
from connect.api.v1.invoice.serializers import InvoiceSerializer
from connect.api.v1.metadata import Metadata
from connect.common.models import Invoice, Organization, BillingPlan
from connect import utils
from connect.billing.gateways.stripe_gateway import StripeGateway

from django.http import JsonResponse


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
        invoice_id = request.query_params.get("invoice_id")
        invoice = get_object_or_404(organization.organization_billing_invoice, invoice_random_id=invoice_id)
        flow_instance = utils.get_grpc_types().get("flow")
        invoice_data = {
            "billing_date": invoice.due_date,
            "invoice_date": timezone.now().strftime("%Y-%m-%d"),
            "plan": organization.organization_billing.plan,
            "invoice_id": invoice.invoice_random_id,
            'total_invoice_amount': invoice.total_invoice_amount
        }
        before = str(request.query_params.get("before") + " 00:00")
        after = str(request.query_params.get("after") + " 00:00")
        payment_data = {
            'payment_method': invoice.payment_method,
            'projects': [],
        }
        for project in organization.project.all():
            contact_count = flow_instance.get_billing_total_statistics(
                project_uuid=str(project.flow_organization),
                before=before,
                after=after,
            ).get("active_contacts")
            payment_data['projects'].append(
                {
                    'project_name': project.name,
                    'contact_count': contact_count,
                    'price': BillingPlan.calculate_amount(contact_count)
                }
            )
            client_data = StripeGateway().get_user_detail_data(organization.organization_billing.stripe_customer)
        return JsonResponse(data={
            "payment_data": payment_data,
            "invoice": invoice_data,
            "client_data": client_data
        }, status=status.HTTP_200_OK)
