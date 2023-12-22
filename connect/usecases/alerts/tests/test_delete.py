from django.test import TestCase
from django.conf import settings

from .alerts_factory import AlertFactory
from ..delete import delete_alert
from connect.alerts.models import Alert


class TestDeleteAlert(TestCase):
    def setUp(self):
        self.alert = AlertFactory.create()
        self.token = settings.VERIFICATION_MARKETING_TOKEN

    def test_delete_alert(self):
        delete_alert(
            alert_uuid=self.alert.uuid,
            token=self.token
        )

        self.assertEqual(Alert.objects.count(), 0)
