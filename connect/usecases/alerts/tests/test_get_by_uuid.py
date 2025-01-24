import uuid as uuid4

from django.test import TestCase
from django.conf import settings
from django.core.exceptions import ValidationError

from .alerts_factory import AlertFactory
from ..get_by_uuid import get_alert_by_uuid
from ..exceptions import (
    AlertNotFound,
)


class GetAlertByUuidTestCase(TestCase):
    def setUp(self):
        self.alert = AlertFactory()
        self.token = settings.VERIFICATION_MARKETING_TOKEN

    def test_get_alert_by_uuid(self):

        alert_from_usecase = get_alert_by_uuid(uuid=self.alert.uuid, token=self.token)

        self.assertEqual(alert_from_usecase, self.alert)

    def test_get_by_uuid_nonexistent(self):
        with self.assertRaises(ValidationError):
            get_alert_by_uuid("nonexistent_uuid", self.token)

    def test_get_by_uuid_invalid(self):
        with self.assertRaises(ValidationError):
            get_alert_by_uuid(uuid4.uuid4, self.token)

    def test_get_by_uuid_none(self):
        with self.assertRaises(AlertNotFound):
            get_alert_by_uuid(None, self.token)
