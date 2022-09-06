import requests

from django.contrib.auth import get_user_model
from django.conf import settings

from rest_framework import viewsets
from rest_framework import status
from rest_framework import pagination
from rest_framework.response import Response
from rest_framework.decorators import action

from connect.common.models import TemplateMessage

User = get_user_model()


class TemplateMessageViewSet(viewsets.Viewset):
    lookup_field = "uuid"
    queryset = TemplateMessage.objects.all()

    def get_queryset(self, *args, **kwargs):
        return self.queryset

    @action(methods={"GET"})
    def get_last_template_sync(self, request, uuid=None):
        if not uuid:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        response = requests.get(url=f"{settings.FLOWS_URL}/get_last_template_sync/{uuid}").json()

        return Response(data=response)