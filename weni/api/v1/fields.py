from rest_framework import serializers


class PasswordField(serializers.CharField):
    def __init__(self, *args, **kwargs):
        kwargs.pop("trim_whitespace", None)
        super().__init__(trim_whitespace=False, **kwargs)
