import pytz
import six
from rest_framework import serializers
from rest_framework.exceptions import ValidationError


class PasswordField(serializers.CharField):
    def __init__(self, *args, **kwargs):
        kwargs.pop("trim_whitespace", None)
        super().__init__(trim_whitespace=False, **kwargs)


class ModelMultipleChoiceField(serializers.ManyRelatedField):
    pass


class TextField(serializers.CharField):
    pass


class EntityText(serializers.CharField):
    pass


class TimezoneField(serializers.Field):
    def to_representation(self, obj):
        return six.text_type(obj)

    def to_internal_value(self, data):
        try:
            return pytz.timezone(str(data))
        except pytz.exceptions.UnknownTimeZoneError:
            raise ValidationError("Unknown timezone")


# class OrganizationBillingRelatedField(serializers.ModelSerializer):
#     def to_representation(self, value):
#         print(value)
#         # version = BillingPlan.objects.get(
#         #     pk=int(value.pk)
#         # ).repository_version.pk
#         # return version
