import filetype
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from keycloak import KeycloakGetError
from rest_framework import mixins, permissions, parsers
from rest_framework.decorators import action
from rest_framework.exceptions import UnsupportedMediaType, ValidationError
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from weni.api.v1.account.serializers import (
    UserSerializer,
    UserPhotoSerializer,
    ChangePasswordSerializer,
)
from weni.api.v1.keycloak import KeycloakControl
from weni.authentication.models import User
from weni.utils import upload_photo_rocket


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
            for service in self.request.user.service_status.filter(
                service__rocket_chat=True
            ):
                upload_photo_rocket(
                    server_rocket=service.service.url,
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
        except KeycloakGetError:
            if not settings.DEBUG:
                raise ValidationError(
                    _("System temporarily unavailable, please try again later.")
                )

        return Response()
