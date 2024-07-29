from typing import Dict

from django.test import TestCase
from connect.sentry.filters import filter_events


class SentryTestCase(TestCase):
    def setUp(self) -> None:
        self.events_to_filter = ["TransportException"]

    def test_filter_event(self):
        event = {"exception": {"values": [{"type": "TransportException"}]}}
        event_result: Dict | None = filter_events(event, {}, self.events_to_filter)
        self.assertIsNone(event_result)

    def test_event_not_in_filter(self):
        event = {"exception": {"values": [{"type": "Exception"}]}}
        event_result: Dict | None = filter_events(event, {}, self.events_to_filter)
        self.assertDictEqual(event_result, event)

    def test_empty_list(self):
        event = {"exception": {"values": []}}
        event_result: Dict | None = filter_events(event, {}, self.events_to_filter)
        self.assertDictEqual(event_result, event)
