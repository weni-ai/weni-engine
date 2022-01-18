import stripe
from connect.billing import Gateway, GatewayNotConfigured
from django.conf import settings


class StripeGateway(Gateway):
    default_currency = "USD"
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
            return {"status": "FAILURE", "response": "Customer does not have a configured card"}
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
            if options and options.get("card_id") and str(card["id"]) == str(
                options.get("card_id")
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
            cards = stripe.PaymentMethod.list(
                customer=identification,
                type='card'
            )
            response = []
            for card in cards.get('data'):
                response.append({'last2': card['card']['last4'][2:], 'brand': card['card']['brand']})
        except self.stripe.error.CardError as error:
            return {"status": "FAILURE", "response": error}
        except self.stripe.error.InvalidRequestError:
            return {"status": "FAILURE", "response": f"No such customer: {identification}"}
        return {"status": "SUCCESS", "response": response}

    def get_user_detail_data(self, identification: str):
        try:
            client_data = stripe.Customer.retrieve(identification)
            response = {
                'name': client_data['name'] if client_data and 'name' in client_data else None,
                'address': client_data['address']

            }
        except self.stripe.error.InvalidRequestError:
            return {"status": "FAILURE", "response": f"No such Customer: {identification}"}
        return {"status": "SUCCESS", "response": response}

    def get_payment_method_details(self, stripe_charge_id: str):
        try:
            charge = stripe.Charge.retrieve(stripe_charge_id)
            card_data = charge['payment_method_details']['card']
            response = {
                'last4': card['last4'],
                'brand': card['brand'],
                'exp_month': card['exp_month'],
                'exp_year': card['exp_year']
            }
        except self.stripe.error.InvalidRequestError:
            return {'response': f'No such Charge id: {stripe_charge_id}', 'status': 'FAIL'}
        return {'response': response, 'status': 'OK'}
