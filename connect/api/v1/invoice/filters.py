from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import ugettext_lazy as _
from django_filters import rest_framework as filters
from rest_framework.exceptions import NotFound
from rest_framework.exceptions import PermissionDenied

from connect.common.models import Invoice, Organization


class InvoiceFilter(filters.FilterSet):
    class Meta:
        model = Invoice
        fields = ["organization"]

    organization = filters.CharFilter(
        field_name="organization",
        method="filter_organization_uuid",
        help_text=_("Organization's UUID"),
        required=True,
    )
    start_due_date = filters.DateFilter(lookup_expr="gte", field_name="due_date")
    end_due_date = filters.DateFilter(lookup_expr="lte", field_name="due_date")
    payment_status = filters.ChoiceFilter(
        choices=Invoice.PAYMENT_STATUS_CHOICES, field_name="payment_status"
    )

    def filter_organization_uuid(self, queryset, name, value):  # pragma: no cover
        request = self.request
        try:
            organization = Organization.objects.get(uuid=value)
            authorization = organization.get_user_authorization(request.user)
            if not authorization.can_read:
                raise PermissionDenied()
            return queryset.filter(organization=organization)
        except Organization.DoesNotExist:
            raise NotFound(_("Organization {} does not exist").format(value))
        except DjangoValidationError:
            raise NotFound(_("Invalid organization UUID"))
