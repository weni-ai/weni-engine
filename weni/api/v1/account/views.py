import filetype
from django.utils.translation import ugettext_lazy as _
from rest_framework import mixins, permissions, parsers
from rest_framework.decorators import action
from rest_framework.exceptions import UnsupportedMediaType
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from weni.api.v1.account.serializers import UserSerializer, UserPhotoSerializer
from weni.authentication.models import User


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
    def upload_photo(self, request, **kwargs):
        f = request.FILES.get("file")

        serializer = UserPhotoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if filetype.is_image(f):
            self.request.user.photo = f
            self.request.user.save(update_fields=["photo"])
            return Response({"photo": self.request.user.photo.url})
        raise UnsupportedMediaType(
            filetype.get_type(f.content_type).extension,
            detail=_("Unauthorized file type, upload an image file"),
        )

    @action(
        detail=True,
        methods=["DELETE"],
        url_name="profile-upload-photo",
        parser_classes=[parsers.MultiPartParser],
    )
    def delete_photo(self, request, **kwargs):
        self.request.user.photo.storage.delete(self.request.user.photo.name)
        self.request.user.photo = None
        self.request.user.save(update_fields=["photo"])
        return Response({})
