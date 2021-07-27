import stripe
from weni.billing import Gateway, GatewayNotConfigured
from django.conf import settings


class StripeGateway(Gateway):
    default_currency = "BRL"
    display_name = "Stripe"

    def __init__(self):
        billing_settings = getattr(settings, "BILLING_SETTINGS")
        if not billing_settings or not billing_settings.get("stripe"):
            raise GatewayNotConfigured(
                "The '%s' gateway is not correctly " "configured." % self.display_name
            )
        stripe_settings = billing_settings["stripe"]
        stripe.api_key = stripe_settings["API_KEY"]
        self.stripe = stripe
