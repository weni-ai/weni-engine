from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from weni.authentication.models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "photo"]
        ref_name = None

    username = serializers.CharField(label=_("Username"), read_only=True)
    email = serializers.EmailField(label=_("Email"), read_only=True)
    photo = serializers.ImageField(label=_("User photo"), read_only=True)


class UserPhotoSerializer(serializers.Serializer):
    file = serializers.FileField(required=True)
