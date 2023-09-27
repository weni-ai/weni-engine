import filetype
from django.conf import settings
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from keycloak import KeycloakGetError
from rest_framework import mixins, permissions, parsers
from rest_framework.decorators import action
from rest_framework.exceptions import UnsupportedMediaType, ValidationError
from rest_framework.filters import SearchFilter
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from connect.api.v1.account.serializers import (
    UserSerializer,
    UserPhotoSerializer,
    ChangePasswordSerializer,
    ChangeLanguageSerializer,
    SearchUserSerializer,
    UserEmailSetupSerializer
)
from connect.api.v1.keycloak import KeycloakControl
from connect.authentication.models import User
from connect.common.models import OrganizationAuthorization, Service
from connect.utils import upload_photo_rocket
from connect.celery import app as celery_app
from rest_framework import status
from connect.authentication.models import UserEmailSetup
from django.utils.encoding import force_text
from django.utils.http import urlsafe_base64_decode
from django.shortcuts import get_object_or_404
from connect.authentication.models import generate_token


class MyUserProfileViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    """
    Manager current user profile.
    retrieve:
    Get current user profile
    update:
    Update current user profile.
    partial_update:
    Update, partially, current user profile.
    """

    serializer_class = UserSerializer
    queryset = User.objects
    lookup_field = None
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, *args, **kwargs):
        request = self.request
        user = request.user

        # May raise a permission denied
        self.check_object_permissions(self.request, user)

        return user

    def _get_photo_url(self, user: User) -> str:
        photo = user.photo
        domain = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/"
        endpoint = photo.storage.location + photo.name
        return domain + endpoint

    @action(
        detail=True,
        methods=["POST"],
        url_name="profile-upload-photo",
        parser_classes=[parsers.MultiPartParser],
        serializer_class=UserPhotoSerializer,
    )
    def upload_photo(self, request, **kwargs):  # pragma: no cover
        file = request.FILES.get("file")

        serializer = UserPhotoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if filetype.is_image(file):
            user = self.request.user
            user.photo = file
            user.save(update_fields=["photo"])

            # Update avatar on integrations
            celery_app.send_task("update_user_photo", args=[user.email, self._get_photo_url(user)])

            # Update avatar in all rocket chat registered
            for authorization in user.authorizations_user.all():
                for project in authorization.organization.project.all():
                    for service_status in project.service_status.filter(
                        service__service_type=Service.SERVICE_TYPE_CHAT
                    ):
                        upload_photo_rocket(
                            server_rocket=service_status.service.url,
                            jwt_token=self.request.auth,
                            avatar_url=user.photo.url,
                        )

            return Response({"photo": user.photo.url})
        try:
            raise UnsupportedMediaType(
                filetype.get_type(file.content_type).extension,
                detail=_("We accept images only in the formats: .png, .jpeg, .gif"),
            )
        except Exception:
            raise UnsupportedMediaType(
                None,
                detail=_("We accept images only in the formats: .png, .jpeg, .gif"),
            )

    @action(
        detail=True,
        methods=["DELETE"],
        url_name="profile-upload-photo",
        parser_classes=[parsers.MultiPartParser],
    )
    def delete_photo(self, request, **kwargs):  # pragma: no cover
        self.request.user.photo.storage.delete(self.request.user.photo.name)
        self.request.user.photo = None
        self.request.user.save(update_fields=["photo"])
        return Response({})

    @action(
        detail=True,
        methods=["POST"],
        url_name="profile-change-password",
        serializer_class=ChangePasswordSerializer,
    )
    def change_password(self, request, **kwargs):  # pragma: no cover
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            keycloak_instance = KeycloakControl()

            user_id = keycloak_instance.get_user_id_by_email(
                email=self.request.user.email
            )
            keycloak_instance.instance.set_user_password(
                user_id=user_id, password=request.data.get("password"), temporary=False
            )
            self.request.user.send_change_password_email()
        except KeycloakGetError or ValidationError:
            raise ValidationError(
                _("System temporarily unavailable, please try again later.")
            )

        return Response()

    @action(
        detail=True,
        methods=["PUT", "PATCH"],
        url_name="profile-change-language",
        serializer_class=ChangeLanguageSerializer,
    )
    def change_language(self, request, **kwargs):  # pragma: no cover
        serializer = ChangeLanguageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        language = serializer.data.get("language")
        user = request.user
        user.update_language(language)

        return Response({"language": user.language})

    @action(
        detail=True,
        methods=["PATCH"],
        url_name="two-factor-authentication",
    )
    def set_two_factor_authentication(self, request, **kwargs):
        user = request.user
        activate_2fa = request.data.get("2FA")
        if isinstance(activate_2fa, bool):
            keycloak_instance = KeycloakControl()
            user.has_2fa = activate_2fa
            user.save()
            response = keycloak_instance.configure_2fa(user.email, activate_2fa)
            if response == {}:
                OrganizationAuthorization.set_2fa(user)
                return Response(status=status.HTTP_200_OK, data={"email": user.email})
            else:
                return Response(status=status.HTTP_404_NOT_FOUND, data={"response": response})

    @action(
        detail=True,
        methods=["PUT"],
        url_name="additional-information",
    )
    def add_additional_information(self, request, **kwargs):
        try:

            user = request.user

            company_info = request.data.get("company")
            user_info = request.data.get("user")

            user.company_name = company_info.get("name")
            user.company_segment = company_info.get("segment")
            user.company_sector = company_info.get("sector")
            user.number_people = company_info.get("number_people")
            user.weni_helps = company_info.get("weni_helps")
            user.phone = user_info.get("phone")
            user.position = user_info.get("position")
            user.last_update_profile = timezone.now()

            updated_fields = [
                "company_name",
                "company_sector",
                "number_people",
                "weni_helps",
                "phone",
                "last_update_profile",
                "position"
            ]

            if "utm" in user_info:
                user.utm = user_info.get("utm")
                updated_fields.append("utm")

            user.save(
                update_fields=updated_fields
            )
            data = dict(
                send_request_flow=settings.SEND_REQUEST_FLOW,
                flow_uuid=settings.FLOW_MARKETING_UUID,
                token_authorization=settings.TOKEN_AUTHORIZATION_FLOW_MARKETING
            )
            user.send_request_flow_user_info(data)
            response = dict(
                company=dict(
                    name=user.company_name,
                    sector=user.company_sector,
                    segment=user.company_segment,
                    number_people=user.number_people,
                    weni_helps=user.weni_helps
                ),
                user=dict(
                    phone=user.phone,
                    last_update_profile=user.last_update_profile,
                    position=user.position,
                    utm=user.utm
                )
            )
            return Response(status=200, data=response)
        except Exception as e:
            return Response(status=404, data=dict(error=str(e)))

    @action(
        detail=True,
        methods=["PATCH"],
        url_name="receive-emails",
    )
    def receive_emails(self, request, **kwargs):
        user = request.user
        data = request.data

        try:
            setup = user.email_setup
            if "receive_organization_emails" in data.keys():
                setup.receive_organization_emails = data.get("receive_organization_emails")
                setup.save(update_fields=["receive_organization_emails"])
            if "receive_project_emails" in data.keys():
                setup.receive_project_emails = data.get("receive_project_emails")
                setup.save(update_fields=["receive_project_emails"])
            response = UserEmailSetupSerializer(setup).data
            return Response(status=200, data=response)

        except UserEmailSetup.DoesNotExist:
            data.update(user=user)
            setup = UserEmailSetup.objects.create(**data)
            response = UserEmailSetupSerializer(setup).data
            return Response(status=200, data=response)
        except Exception as e:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR, data={"message": e})

    @action(
        detail=True,
        methods=["POST"],
        url_name="send-email-verification",
    )
    def send_email_verification(self, request, **kwargs):
        user = request.user
        try:
            user.send_email_verify_email()
            return Response(status=200)
        except Exception as e:
            print(e)
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR, data={"message": str(e)})

    @action(
        detail=True,
        methods=["GET"],
        url_path="verify-email/(?P<uidb64>[^/.]+)/(?P<token>[^/.]+)",
        permission_classes=[permissions.AllowAny]
    )
    def verify_email(self, request, **kwargs):

        uidb64 = kwargs.get("uidb64")
        token = kwargs.get("token")

        try:
            uid = force_text(urlsafe_base64_decode(uidb64))
            user = get_object_or_404(User, pk=uid)

            if generate_token.check_token(user, token):
                user.verify_email()

            return Response(status=200)

        except Exception as e:
            print(e)
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR, data={"message": str(e)})

    @action(
        detail=True,
        methods=["GET"],
        url_name="user-company-info",
        url_path="user-company-info",
    )
    def get_user_company_info(self, request, **kwargs):
        user = self.request.user
        authorizations = user.authorizations_user
        if authorizations.count() == 1:
            organization = authorizations.first().organization
            first_user = organization.authorizations.order_by("created_at").first().user
            if first_user.id != user.id:
                organization = dict(
                    uuid=str(organization.uuid),
                    name=organization.name,
                    authorization=authorizations.first().role
                )
                company = dict(
                    company_name=first_user.company_name,
                    company_segment=first_user.company_segment,
                    company_sector=first_user.company_sector,
                    number_people=first_user.number_people,
                    weni_helps=first_user.weni_helps
                )
                data = dict(
                    organization=organization,
                    company=company
                )
                return Response(status=status.HTTP_200_OK, data=data)

        return Response(status=status.HTTP_200_OK, data={})


class SearchUserViewSet(mixins.ListModelMixin, GenericViewSet):  # pragma: no cover
    serializer_class = SearchUserSerializer
    queryset = User.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter]
    permission_classes = [permissions.IsAuthenticated]
    search_fields = [
        "=first_name",
        "^first_name",
        "$first_name",
        "=last_name",
        "^last_name",
        "$last_name",
        "=last_name",
        "^username",
        "$username",
        "=email",
        "^email",
        "$email",
    ]
    pagination_class = None
    limit = 5

    def list(self, request, *args, **kwargs):
        if len(request.query_params.get("search", "")) == 0:
            raise ValidationError(
                _("The search field needed the text to search.")
            )
        queryset = self.filter_queryset(self.get_queryset())[: self.limit]
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
