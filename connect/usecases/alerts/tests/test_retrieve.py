from django.test import TestCase
from django.conf import settings

from .alerts_factory import AlertFactory
from ..retrieve import AlertRetrieveUseCase


class TestRetrieveAlert(TestCase):
    def setUp(self):
        self.usecase = AlertRetrieveUseCase()
        self.alert = AlertFactory.create()
        self.token = settings.VERIFICATION_MARKETING_TOKEN

    def test_retrieve_alert(self):
        alert = self.usecase.retrieve_alert(
            alert_uuid=self.alert.uuid, token=self.token
        )

        self.assertEqual(alert.uuid, self.alert.uuid)
        self.assertEqual(alert.can_be_closed, self.alert.can_be_closed)
        self.assertEqual(alert.text, self.alert.text)
        self.assertEqual(alert.type, self.alert.type)
