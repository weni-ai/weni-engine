from functools import partial

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

from django.apps import AppConfig
from django.conf import settings

from connect.sentry.filters import filter_events


class SentryConfig(AppConfig):
    name = "connect.sentry"

    def ready(self) -> None:
        if not settings.USE_SENTRY:
            return

    if settings.USE_SENTRY:
        sentry_sdk.init(
            dsn=settings.SENTRY_URL,
            integrations=[DjangoIntegration()],
            environment=settings.ENVIRONMENT,
            before_send=partial(
                filter_events, events_to_filter=settings.FILTER_SENTRY_EVENTS
            ),
        )
