import filetype
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
)
from connect.api.v1.keycloak import KeycloakControl
from connect.authentication.models import User
from connect.common.models import Service
from connect.utils import upload_photo_rocket
from connect.celery import app as celery_app


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

    @action(
        detail=True,
        methods=["POST"],
        url_name="profile-upload-photo",
        parser_classes=[parsers.MultiPartParser],
        serializer_class=UserPhotoSerializer,
    )
    def upload_photo(self, request, **kwargs):  # pragma: no cover
        f = request.FILES.get("file")

        serializer = UserPhotoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if filetype.is_image(f):
            self.request.user.photo = f
            self.request.user.save(update_fields=["photo"])

            # Update avatar in all rocket chat registered
            for authorization in self.request.user.authorizations_user.all():
                for project in authorization.organization.project.all():
                    for service_status in project.service_status.filter(
                        service__service_type=Service.SERVICE_TYPE_CHAT
                    ):
                        upload_photo_rocket(
                            server_rocket=service_status.service.url,
                            jwt_token=self.request.auth,
                            avatar_url=self.request.user.photo.url,
                        )

            return Response({"photo": self.request.user.photo.url})
        try:
            raise UnsupportedMediaType(
                filetype.get_type(f.content_type).extension,
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

        user = request.user
        user.language = serializer.data.get("language")
        user.save(update_fields=["language"])

        celery_app.send_task(
            "update_user_language",
            args=[
                user.email,
                user.language,
            ],
        )

        return Response()


class SearchUserViewSet(mixins.ListModelMixin, GenericViewSet):  # pragma: no cover
    serializer_class = UserSerializer
    queryset = User.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter]
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
        queryset = self.filter_queryset(self.get_queryset())[: self.limit]
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
