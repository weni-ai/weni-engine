from rest_framework import mixins
from rest_framework.viewsets import GenericViewSet

from .paginations import ChangeHistoryCursorPagination
from .permissions import (
    HasProjectPermission,
)
from .serializers import (
    ListProjectChangeHistorySerializer,
    RetrieveProjectChangeHistorySerializer,
)
from connect.change_history.models import ChangeEvent


class ProjectChangeHistoryViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet
):
    queryset = ChangeEvent.objects.all()
    pagination_class = ChangeHistoryCursorPagination
    permission_classes = [HasProjectPermission]

    serializers_map = {
        "list": ListProjectChangeHistorySerializer,
        "retrieve": RetrieveProjectChangeHistorySerializer,
    }

    def get_serializer_class(self):
        return self.serializers_map[self.action]

    def get_queryset(self):
        queryset = super().get_queryset().filter(
            project_uuid=self.kwargs["project_uuid"]
        )

        object_name = self.request.query_params.get("object_name")
        if object_name:
            queryset = queryset.filter(object_name__icontains=object_name)

        module = self.request.query_params.get("module")
        if module:
            queryset = queryset.filter(module__iexact=module)

        entity = self.request.query_params.get("entity")
        if entity:
            queryset = queryset.filter(entity__iexact=entity)

        return queryset
