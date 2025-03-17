from rest_framework import serializers

from connect.api.v1.project.serializers import ProjectSerializer
from connect.common.models import Invoice, InvoiceProject


class InvoiceProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceProject
        fields = [
            "invoice",
            "project",
            "amount",
            "contact_count",
        ]
        ref_name = None

    project = ProjectSerializer(many=False, read_only=True)


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = [
            "id",
            "invoice_random_id",
            "due_date",
            "paid_date",
            "discount",
            "payment_status",
            "payment_method",
            "invoice_details",
            "invoice_amount",
            "notes",
            "extra_integration",
            "cost_per_whatsapp",
            "card_data",
        ]
        ref_name = None

    invoice_details = InvoiceProjectSerializer(
        many=True, source="organization_billing_invoice_project"
    )
