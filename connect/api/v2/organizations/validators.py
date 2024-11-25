import validators
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers


class IsHyperlinkValidator(object):
    def __call__(self, value):
        if validators.url(value):
            raise serializers.ValidationError(_("Invalid URL"))
        return value
