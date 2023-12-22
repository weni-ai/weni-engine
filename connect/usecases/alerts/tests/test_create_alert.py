from django.test import TestCase
from django.conf import settings

from ..create import AlertCreateUseCase
from ..exceptions import AlertsPermissionDenied


class CreateAlertTestCase(TestCase):

    def setUp(self):
        self.usecase = AlertCreateUseCase()

    def test_create_alert(self):
        alert = self.usecase.create_alert(
            can_be_closed=True,
            text="This is a test alert",
            type=1,
            token=settings.VERIFICATION_MARKETING_TOKEN,
        )

        self.assertEqual(alert.can_be_closed, True)
        self.assertEqual(alert.text, "This is a test alert")
        self.assertEqual(alert.type, 1)

    def test_create_alert_with_invalid_token(self):
        with self.assertRaises(AlertsPermissionDenied):
            self.usecase.create_alert(
                can_be_closed=True,
                text="This is a test alert",
                type=1,
                token="invalid_token",
            )
