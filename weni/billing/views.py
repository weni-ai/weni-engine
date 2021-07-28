import json
from datetime import datetime

from django.conf import settings
from django.http import HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from weni.common.models import Organization, Invoice, BillingPlan


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

        # if not event.livemode:
        #     return HttpResponse("Ignored, test event")

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
            if invoice and event.type == "charge.failed":
                invoice.rollback()
                invoice.save()

            invoice.stripe_charge = charge.id
            invoice.paid_date = charge_date
            invoice.payment_status = Invoice.PAYMENT_STATUS_PAID
            invoice.payment_method = BillingPlan.PAYMENT_METHOD_CREDIT_CARD
            invoice.save(
                update_fields=[
                    "stripe_charge",
                    "paid_date",
                    "payment_status",
                    "payment_method",
                ]
            )
            return HttpResponse()

        # empty response, 200 lets Stripe know we handled it
        return HttpResponse("Ignored, uninteresting event")
