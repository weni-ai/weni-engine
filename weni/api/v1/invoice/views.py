from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import GenericViewSet

from weni.api.v1.invoice.filters import InvoiceFilter
from weni.api.v1.invoice.serializers import InvoiceSerializer
from weni.api.v1.metadata import Metadata
from weni.common.models import Invoice


class InvoiceViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    queryset = Invoice.objects
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]
    filter_class = InvoiceFilter
    filter_backends = [OrderingFilter, SearchFilter, DjangoFilterBackend]
    lookup_field = "pk"
    metadata_class = Metadata
