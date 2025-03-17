from django.test import TestCase

from .models import Alert


class AlertsTestCase(TestCase):
    def setUp(self):
        self.alert = Alert.objects.create(
            can_be_closed=True,
            text="This is a test alert",
            type=1,
        )

    def test_alerts(self):
        self.assertEqual(self.alert.can_be_closed, True)
        self.assertEqual(self.alert.text, "This is a test alert")
        self.assertEqual(self.alert.type, 1)
