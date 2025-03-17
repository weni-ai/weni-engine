import logging
from django.conf import settings
from rest_framework import viewsets
from rest_framework.decorators import action
import stripe
from stripe.api_resources.customer import Customer
from django.http import JsonResponse
from rest_framework import status
from connect.common.models import BillingPlan
from connect import billing

logger = logging.getLogger(__name__)


class BillingViewSet(viewsets.ViewSet):
    """
    A simple viewset for billing actions
    """

    @action(
        detail=True,
        methods=["POST"],
        url_name="setup-intent",
        url_path="setup-intent",
    )
    def setup_intent(self, request):
        """
        Creates customer and setup intent object for it.
        """
        stripe.api_key = settings.BILLING_SETTINGS.get("stripe", {}).get("API_KEY")

        if settings.TESTING:
            # Customer for unit test, this id dosen't exist
            customer = Customer(id="cus_MYOrndkgpPHGK9")
            # Fake setup intent object
            setup_intent = stripe.SetupIntent(
                customer=customer.id, id="seti_test_string"
            )

        else:
            customer = stripe.Customer.create()
            setup_intent = stripe.SetupIntent.create(customer=customer.id)

        data = {
            "setup_intent": setup_intent,
            "customer": customer.id,
        }
        return JsonResponse(data=data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["POST"],
        url_name="setup-plan",
        url_path="setup-plan",
    )
    def setup_plan(self, request):
        """Make the payment to the selected plan"""
        stripe.api_key = settings.BILLING_SETTINGS.get("stripe", {}).get("API_KEY")

        plan = request.data.get("plan")
        customer = request.data.get("customer")

        plan_info = BillingPlan.plan_info(plan)

        if not plan_info["valid"]:
            return JsonResponse(
                data={"status": "FAILURE", "message": "Invalid plan choice"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        price = BillingPlan.plan_info(plan)["price"]

        data = {
            "customer": customer,
            "plan": plan,
            "price": price,
        }

        if settings.TESTING:
            p_intent = stripe.PaymentIntent(
                amount_received=price,
                id="pi_test_id",
                amount=price,
                charges={"amount": price, "amount_captured": price},
            )
            purchase_result = {"status": "SUCCESS", "response": p_intent}
            data["status"] = "SUCCESS"
        else:
            try:
                from decimal import Decimal
                import decimal

                price -= price * (4.18 / 100)
                final_price = Decimal(price).quantize(
                    Decimal(".01"), decimal.ROUND_HALF_UP
                )
                gateway = billing.get_gateway("stripe")
                purchase_result = gateway.purchase(
                    money=int(final_price),
                    identification=customer,
                )
                data["status"] = purchase_result["status"]
            except Exception as error:
                logger.error(f"Stripe error: {error}")
                data["status"] = "FAILURE"

        return JsonResponse(data=data, status=status.HTTP_200_OK)
