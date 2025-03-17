from django.test import TestCase
from django.conf import settings

from .alerts_factory import AlertFactory
from ..update import AlertUpdateUseCase


class TestUpdateAlert(TestCase):
    def setUp(self):
        self.usecase = AlertUpdateUseCase()
        self.alert = AlertFactory.create()
        self.token = settings.VERIFICATION_MARKETING_TOKEN

    def test_update_alert(self):
        alert = self.usecase.update_alert(
            alert_uuid=self.alert.uuid,
            token=self.token,
            can_be_closed=False,
            text="test",
            type=2,
        )

        self.assertEqual(alert.can_be_closed, False)
        self.assertEqual(alert.text, "test")
        self.assertEqual(alert.type, 2)
