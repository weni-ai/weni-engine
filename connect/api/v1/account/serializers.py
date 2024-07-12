from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers
from keycloak import exceptions

from connect.api.v1.fields import PasswordField
from connect.api.v1.keycloak import KeycloakControl
from connect.authentication.models import User, UserEmailSetup
from connect.common.models import OrganizationAuthorization

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
            "company_phone_number",
            "last_update_profile",
            "utm",
            "email_marketing",
            "has_2fa",
            "send_email_setup",
            "can_update_password"
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
    company_phone_number = serializers.IntegerField(
        required=False,
        label=_("Company Telephone Number"),
        help_text=_("Company phone number of the user; include area code"),
    )
    last_update_profile = serializers.DateTimeField(read_only=True)
    utm = serializers.JSONField(required=False, initial=dict)
    email_marketing = serializers.BooleanField(required=False)
    send_email_setup = serializers.SerializerMethodField()
    can_update_password = serializers.SerializerMethodField()

    def update(self, instance, validated_data):
        instance.last_update_profile = timezone.now()
        update_instance = super().update(
            instance=instance, validated_data=validated_data
        )
        if "phone" in validated_data or "short_phone_prefix" in validated_data:
            data = dict(
                send_request_flow=settings.SEND_REQUEST_FLOW,
                flow_uuid=settings.FLOW_MARKETING_UUID,
                token_authorization=settings.TOKEN_AUTHORIZATION_FLOW_MARKETING
            )
            instance.send_request_flow_user_info(data)

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

            self.keycloak_update(update_instance)

        return update_instance

    def get_can_update_password(self, obj):
        if not obj.identity_provider.exists():
            return True
        auth_orgs = OrganizationAuthorization.objects.filter(
            user=obj,
            organization__require_external_provider_for_access=True
        )
        return not auth_orgs.exists()

    def get_send_email_setup(self, obj):
        try:
            setup = obj.email_setup
            return UserEmailSetupSerializer(setup).data
        except Exception:
            return {}

    def keycloak_update(self, update_instance):
        try:
            keycloak_instance = KeycloakControl()

            user_id = keycloak_instance.get_user_id_by_email(email=update_instance.email)
            keycloak_instance.get_instance().update_user(
                user_id=user_id,
                payload={
                    "firstName": update_instance.first_name,
                    "lastName": update_instance.last_name,
                },
            )
        except exceptions.KeycloakGetError as error:
            return error
        return True


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


class UserEmailSetupSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserEmailSetup
        fields = ["receive_organization_emails", "receive_project_emails"]
