from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from connect.api.v1.fields import PasswordField
from connect.authentication.models import User

from connect.api.v1.internal.chats.chats_rest_client import ChatsRESTClient
from connect.api.v1.internal.integrations.integrations_rest_client import IntegrationsRESTClient


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
            "last_update_profile",
            "utm",
            "email_marketing",
            "has_2fa"
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
    last_update_profile = serializers.DateTimeField(read_only=True)
    utm = serializers.JSONField(required=False, initial=dict)
    email_marketing = serializers.BooleanField(required=False)

    def update(self, instance, validated_data):
        instance.last_update_profile = timezone.now()
        update_instance = super().update(
            instance=instance, validated_data=validated_data
        )
        if "phone" in validated_data or "short_phone_prefix" in validated_data:
            instance.send_request_flow_user_info()

        if "first_name" in validated_data or "last_name" in validated_data:

            integrations_client = IntegrationsRESTClient()
            chats_client = ChatsRESTClient()

            integrations_client.update_user(
                user_email=update_instance.email,
                first_name=update_instance.first_name,
                last_name=update_instance.last_name
            )
            chats_client.update_user(
                user_email=update_instance.email,
                first_name=update_instance.first_name,
                last_name=update_instance.last_name
            )

        return update_instance


class UserPhotoSerializer(serializers.Serializer):
    file = serializers.FileField(required=True)


class ChangePasswordSerializer(serializers.Serializer):
    password = PasswordField(
        write_only=True, validators=[validate_password], label=_("Password")
    )


class ChangeLanguageSerializer(serializers.Serializer):
    language = serializers.ChoiceField(settings.LANGUAGES, label=_("Language"))


class SearchUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "photo",
        ]
