from django.contrib.auth import get_user_model
from django.conf import settings

from rest_framework import viewsets
from rest_framework import status
from rest_framework import pagination
from rest_framework.response import Response
from rest_framework.decorators import action

from connect.common.models import TemplateMessage

User = get_user_model()


class TemplateMessageViewSet(viewsets.ModelViewSet):
    lookup_field = "uuid"
    queryset = TemplateMessage.objects.all()

    def get_queryset(self, *args, **kwargs):
        return self.queryset