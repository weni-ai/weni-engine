from django.test import TestCase
from django.conf import settings

from .alerts_factory import AlertFactory
from ..list import AlertListUseCase


class TestListAlerts(TestCase):
    def setUp(self):
        self.usecase = AlertListUseCase()
        self.alert = AlertFactory()
        self.token = settings.VERIFICATION_MARKETING_TOKEN

    def test_list_alerts(self):

        alerts_from_usecase = self.usecase.list_alerts(token=self.token)

        self.assertEqual(alerts_from_usecase[0], self.alert)
