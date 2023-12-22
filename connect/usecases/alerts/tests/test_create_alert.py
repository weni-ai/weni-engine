from django.test import TestCase
from django.conf import settings

from ..create import create_alert
from ..exceptions import AlertsPermissionDenied


class CreateAlertTestCase(TestCase):

    def test_create_alert(self):
        alert = create_alert(
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
            create_alert(
                can_be_closed=True,
                text="This is a test alert",
                type=1,
                token="invalid_token",
            )
