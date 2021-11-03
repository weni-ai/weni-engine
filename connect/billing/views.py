import json
from datetime import datetime

from django.conf import settings
from django.http import HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from connect import billing
from connect.common.models import Organization, Invoice, BillingPlan


class StripeHandler(View):  # pragma: no cover
    """
    Handles WebHook events from Stripe.  We are interested as to when invoices are
    charged by Stripe so we can send the user an invoice email.
    """

    @csrf_exempt
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request, *args, **kwargs):
        return HttpResponse("ILLEGAL METHOD")

    def post(self, request, *args, **kwargs):
        import stripe

        # from temba.orgs.models import Org, TopUp

        # stripe delivers a JSON payload
        stripe_data = json.loads(request.body)

        # but we can't trust just any response, so lets go look up this event
        stripe.api_key = settings.BILLING_SETTINGS.get("stripe", {}).get("API_KEY")
        event = stripe.Event.retrieve(stripe_data["id"])

        if not event:
            return HttpResponse("Ignored, no event")

        if not event.livemode and settings.BILLING_TEST_MODE:
            return HttpResponse("Ignored, test event")

        # we only care about invoices being paid or failing
        if event.type == "charge.succeeded" or event.type == "charge.failed":
            charge = event.data.object
            charge_date = datetime.fromtimestamp(charge.created).date()
            invoice_id = charge.metadata.get("id")

            # look up our customer
            customer = stripe.Customer.retrieve(charge.customer)

            # and our org
            org = Organization.objects.filter(
                organization_billing__stripe_customer=customer.id
            ).first()
            if not org:
                return HttpResponse("Ignored, no org for customer")

            # look up the topup that matches this charge
            invoice = Invoice.objects.filter(pk=invoice_id).first()
            if event.type == "charge.failed":
                if invoice:
                    invoice.rollback()
                    invoice.save()
                return HttpResponse("Ignored, charge failed")

            update_fields = [
                "payment_status",
                "payment_method",
            ]
            invoice.payment_method = BillingPlan.PAYMENT_METHOD_CREDIT_CARD
            if not charge.disputed:
                invoice.paid_date = charge_date
                invoice.payment_status = Invoice.PAYMENT_STATUS_PAID
                invoice.stripe_charge = charge.id
                update_fields.append("paid_date")
                update_fields.append("stripe_charge")
            else:
                invoice.payment_status = Invoice.PAYMENT_STATUS_FRAUD
            invoice.save(update_fields=update_fields)
            return HttpResponse()
        elif event.type == "payment_method.attached":
            customer = stripe_data.get("data", {}).get("object", {}).get("customer")
            card_id = stripe_data.get("data", {}).get("object", {}).get("id")
            card_info = stripe_data.get("data", {}).get("object", {}).get("card", {})
            billing_details = (
                stripe_data.get("data", {}).get("object", {}).get("billing_details", {})
            )

            org = BillingPlan.objects.filter(stripe_customer=customer).first()
            if not org:
                return HttpResponse("Ignored, no org for customer")

            # Remove old registered cards and leave only the new card added
            gateway = billing.get_gateway("stripe")
            gateway.unstore(identification=customer, options={"card_id": card_id})

            ###############################################################

            org.stripe_configured_card = True
            org.final_card_number = card_info.get("last4")
            org.card_expiration_date = (
                f"{card_info.get('exp_month')}/{card_info.get('exp_year')}"
            )
            org.cardholder_name = billing_details.get("name")
            org.card_brand = card_info.get("brand")
            org.save(
                update_fields=[
                    "stripe_configured_card",
                    "final_card_number",
                    "card_expiration_date",
                    "cardholder_name",
                    "card_brand",
                ]
            )
            org.allow_payments()

        # empty response, 200 lets Stripe know we handled it
        return HttpResponse("Ignored, uninteresting event")
