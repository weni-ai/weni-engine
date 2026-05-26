"""Serializers for the business verification notification endpoint."""

from django.conf import settings
from rest_framework import serializers


VALID_STATUSES = ("APPROVED", "FAILED")


class NotifyBusinessVerificationSerializer(serializers.Serializer):
    """Input payload sent by the integrations-engine to dispatch the result email."""

    user_email = serializers.EmailField(required=True)
    status = serializers.ChoiceField(choices=VALID_STATUSES, required=True)
    rejection_reasons = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
    )
    verification_attempts = serializers.IntegerField(required=False, default=0, min_value=0)
    language = serializers.ChoiceField(
        choices=settings.LANGUAGES,
        required=False,
        allow_null=True,
        default=None,
    )
