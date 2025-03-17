from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import GenericViewSet
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from django.utils import timezone
from connect.api.v1.invoice.filters import InvoiceFilter
from connect.api.v1.invoice.serializers import InvoiceSerializer
from connect.api.v1.metadata import Metadata
from connect.common.models import Invoice, Organization, BillingPlan, GenericBillingData
from connect.billing.gateways.stripe_gateway import StripeGateway
from connect.utils import count_contacts
from django.http import JsonResponse
from datetime import timedelta

from connect.api.v1.organization.permissions import (
    OrganizationHasPermissionBilling,
)


class InvoiceViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet,
):

    queryset = Invoice.objects
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated, OrganizationHasPermissionBilling]
    filter_class = InvoiceFilter
    filter_backends = [OrderingFilter, SearchFilter, DjangoFilterBackend]
    lookup_field = "pk"
    metadata_class = Metadata

    @action(
        detail=True,
        methods=["GET"],
        url_name="invoice-data",
        url_path="invoice-data/(?P<organization_uuid>[^/.]+)",
        permission_classes=[IsAuthenticated, OrganizationHasPermissionBilling],
    )
    def invoice_data(self, request, organization_uuid):
        organization = get_object_or_404(Organization, uuid=organization_uuid)
        self.check_object_permissions(self.request, organization)
        invoice_id = request.query_params.get("invoice_id")
        invoice = get_object_or_404(
            organization.organization_billing_invoice, invoice_random_id=invoice_id
        )
        billing_data = GenericBillingData.get_generic_billing_data_instance()
        precification = billing_data.precification
        invoice_data = {
            "billing_date": invoice.due_date,
            "invoice_date": timezone.now().strftime("%Y-%m-%d"),
            "plan": organization.organization_billing.plan,
            "invoice_id": invoice.invoice_random_id,
            "total_invoice_amount": invoice.total_invoice_amount,
            "currency": precification["currency"],
        }
        before = invoice.due_date.strftime("%Y-%m-%d %H:%M")
        after = (invoice.due_date - timedelta(days=30)).strftime("%Y-%m-%d %H:%M")
        payment_details_result = StripeGateway().get_payment_method_details(
            invoice.stripe_charge
        )
        card_data = (
            {
                "brand": payment_details_result["response"]["brand"],
                "final_card_number": payment_details_result["response"][
                    "final_card_number"
                ],
            }
            if payment_details_result["status"] == "SUCCESS"
            else {"message": "stripe charge not found!"}
        )
        payment_data = {
            "payment_method": invoice.payment_method,
            "card_data": card_data,
            "projects": [],
        }
        contact_count = 0
        for project in organization.project.all():
            current_contact_count = count_contacts(
                project=project, before=before, after=after
            )
            contact_count += current_contact_count
            payment_data["projects"].append(
                {
                    "project_name": project.name,
                    "contact_count": current_contact_count,
                }
            )
            client_data = StripeGateway().get_user_detail_data(
                organization.organization_billing.stripe_customer
            )
        payment_data["price"] = BillingPlan.calculate_amount(contact_count)
        return JsonResponse(
            data={
                "payment_data": payment_data,
                "invoice": invoice_data,
                "client_data": client_data,
            },
            status=status.HTTP_200_OK,
        )
