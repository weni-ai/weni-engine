import stripe
from connect.billing import Gateway, GatewayNotConfigured
from django.conf import settings


class StripeGateway(Gateway):
    default_currency = settings.DEFAULT_CURRENCY
    display_name = "Stripe"
    verification_amount = getattr(settings, "VERIFICATION_AMOUNT")
    verification_description = "Card Verification Charge"

    def __init__(self):
        billing_settings = getattr(settings, "BILLING_SETTINGS")
        if not billing_settings or not billing_settings.get("stripe"):
            raise GatewayNotConfigured(
                "The '%s' gateway is not correctly " "configured." % self.display_name
            )
        stripe_settings = billing_settings["stripe"]
        stripe.api_key = stripe_settings["API_KEY"]
        self.stripe = stripe

    def authorize(self, identification, options: dict = None):
        try:
            resp = self.stripe.SetupIntent.create(customer=identification)
            return {"status": "SUCCESS", "response": resp}
        except self.stripe.error.InvalidRequestError as error:
            return {"status": "FAILURE", "response": error}

    def purchase(self, money: float, identification, options: dict = None):
        try:
            payment = stripe.PaymentMethod.list(
                customer=identification,
                type="card",
            )
            response = stripe.PaymentIntent.create(
                amount=int(money * 100),
                currency=self.default_currency.lower(),
                customer=identification,
                payment_method=payment.get("data", {})[0].get("id"),
                off_session=True,
                confirm=True,
                metadata=options,
            )
        except IndexError:
            return {
                "status": "FAILURE",
                "response": "Customer does not have a configured card",
            }
        except self.stripe.error.CardError as error:
            return {"status": "FAILURE", "response": error}
        return {"status": "SUCCESS", "response": response}

    def unstore(self, identification, options: dict = None):
        response = []

        existing_cards = stripe.PaymentMethod.list(
            customer=identification,
            type="card",
        )
        for card in existing_cards.get("data"):
            if (
                options
                and options.get("card_id")
                and str(card["id"]) == str(options.get("card_id"))
            ):
                continue
            response.append(
                stripe.PaymentMethod.detach(
                    card.get("id"),
                )
            )
        return {"status": "SUCCESS", "response": response}

    def get_card_data(self, identification, options: dict = None):
        try:
            cards = stripe.PaymentMethod.list(customer=identification, type="card")
            response = []
            for card in cards.get("data"):
                # print(F"CARD: {card}")
                response.append(
                    {
                        "last2": card["card"]["last4"][2:],
                        "brand": card["card"]["brand"],
                        "cardholder_name": card["billing_details"]["name"],
                        "card_expiration_date": f"{card['card']['exp_month']}/{str(card['card']['exp_year'])[2:]}"
                    }
                )
        except self.stripe.error.CardError as error:
            return {"status": "FAILURE", "response": error}
        except self.stripe.error.InvalidRequestError:
            return {
                "status": "FAILURE",
                "response": f"No such customer: {identification}",
            }
        return {"status": "SUCCESS", "response": response}

    def get_user_detail_data(self, identification: str):
        try:
            client_data = stripe.Customer.retrieve(identification)
            response = {
                "name": client_data["name"]
                if client_data and "name" in client_data
                else None,
                "address": client_data["address"],
            }
        except self.stripe.error.InvalidRequestError:
            return {
                "status": "FAILURE",
                "response": f"No such Customer: {identification}",
            }
        return {"status": "SUCCESS", "response": response}

    def get_payment_method_details(self, stripe_charge_id: str):
        try:
            charge = stripe.Charge.retrieve(stripe_charge_id)
            card_data = charge["payment_method_details"]["card"]
            response = {
                "final_card_number": card_data["last4"],
                "brand": card_data["brand"],
            }
        except self.stripe.error.InvalidRequestError:
            return {
                "response": f"No such Charge id: {stripe_charge_id}",
                "status": "FAIL",
            }
        return {"response": response, "status": "SUCCESS"}

    def verify_payment_method(self, customer):
        payment_method = self.stripe.Customer.list_payment_methods(
            customer,
            type="card"
        )
        data = payment_method["data"][0]
        response = {
            "cvc_check": '',
            "address_postal_code_check": ''
        }
        if data["card"]["checks"].get("cvc_check") == "pass":
            response["cvc_check"] = data["card"]["checks"].get("cvc_check")
            response["address_postal_code_check"] = data["card"]["checks"].get("address_postal_code_check")
            return response

        response["cvc_check"] = data["card"]["checks"].get("cvc_check")
        response["address_postal_code_check"] = data["card"]["checks"].get("address_postal_code_check")
        return response

    def card_verification_charge(self, customer):  # pragma: no cover
        try:
            payment = stripe.PaymentMethod.list(
                customer=customer,
                type="card",
            )
            response = stripe.PaymentIntent.create(
                amount=100 * int(self.verification_amount),
                currency='usd',
                customer=customer,
                description="Card Verification Charge",
                payment_method=payment.get("data", {})[0].get("id"),
                off_session=True,
                confirm=True,
            )
            return {
                "status": "SUCCESS",
                "response": response["charges"]["data"][0]["paid"]
            }
        except IndexError:
            return {
                "status": "FAILURE",
                "response": "Customer does not have a configured card",
            }
        except self.stripe.error.CardError as error:
            return {"status": "FAILURE", "response": error}
