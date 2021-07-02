from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from weni.api.v1.fields import PasswordField
from weni.authentication.models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "photo",
            "language",
            "short_phone_prefix",
            "phone",
        ]
        ref_name = None

    id = serializers.IntegerField(label=_("ID"), read_only=True)
    username = serializers.CharField(label=_("Username"), read_only=True)
    email = serializers.EmailField(label=_("Email"), read_only=True)
    photo = serializers.ImageField(label=_("User photo"), read_only=True)
    short_phone_prefix = serializers.IntegerField(
        required=False,
        label=_("Phone Prefix Country"),
        help_text=_("Phone prefix of the user"),
    )
    phone = serializers.IntegerField(
        required=False,
        label=_("Telephone Number"),
        help_text=_("Phone number of the user; include area code"),
    )

    def update(self, instance, validated_data):
        print(validated_data)
        user_phone = instance.phone
        update_instance = super().update(
            instance=instance, validated_data=validated_data
        )
        print(user_phone)
        if (
            "phone" in validated_data or "short_phone_prefix" in validated_data
        ) and user_phone is None:
            print("aa")
            instance.send_request_flow_user_info()
        return update_instance


class UserPhotoSerializer(serializers.Serializer):
    file = serializers.FileField(required=True)


class ChangePasswordSerializer(serializers.Serializer):
    password = PasswordField(
        write_only=True, validators=[validate_password], label=_("Password")
    )


class ChangeLanguageSerializer(serializers.Serializer):
    language = serializers.ChoiceField(settings.LANGUAGES, label=_("Language"))
