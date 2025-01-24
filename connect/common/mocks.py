class StripeMockGateway:
    def get_card_data(self, identification, options: dict = None):
        response = [
            {
                "last2": "42",
                "brand": "visa",
                "cardholder_name": "Lorem Ipsum",
                "card_expiration_date": "12/56",
            }
        ]
        return {"response": response, "status": "SUCCESS"}

    def get_payment_method_details(self, stripe_charge_id: str):
        response = {
            "final_card_number": 1234,
            "brand": "brand",
        }
        return {"response": response, "status": "SUCCESS"}

    def get_user_detail_data(self, identification: str):
        return {"status": "SUCCESS", "response": {}}
