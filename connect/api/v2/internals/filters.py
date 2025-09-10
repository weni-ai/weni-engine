from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import ugettext_lazy as _
from django_filters import rest_framework as filters
from rest_framework.exceptions import NotFound

from connect.common.models import Organization, Project, BillingPlan


class CRMOrganizationFilter(filters.FilterSet):
    """Filter class for CRM Organization endpoint with comprehensive filtering"""

    class Meta:
        model = Organization
        fields = []

    organization_uuid = filters.UUIDFilter(
        field_name="uuid",
        help_text=_("Filter by specific organization UUID"),
    )

    project_uuid = filters.UUIDFilter(
        method="filter_by_project_uuid",
        help_text=_(
            "Filter by project UUID - returns the organization containing that project with all its projects"
        ),
    )

    has_vtex_account = filters.BooleanFilter(
        method="filter_has_vtex_account",
        help_text=_(
            "Filter organizations that have projects with vtex_account (true/false)"
        ),
    )

    created_after = filters.DateFilter(
        field_name="created_at",
        lookup_expr="gte",
        help_text=_("Organizations created after this date (format: DD-MM-YYYY)"),
        input_formats=["%d-%m-%Y"],
    )

    created_before = filters.DateFilter(
        field_name="created_at",
        lookup_expr="lte",
        help_text=_("Organizations created before this date (format: DD-MM-YYYY)"),
        input_formats=["%d-%m-%Y"],
    )

    is_suspended = filters.BooleanFilter(
        method="filter_is_suspended",
        help_text=_("Filter organizations that are suspended (true/false)"),
    )

    plan = filters.ChoiceFilter(
        field_name="organization_billing__plan",
        choices=BillingPlan.PLAN_CHOICES,
        help_text=_("Filter organizations by billing plan (free, trial, start, scale, advanced, enterprise)"),
    )

    def filter_is_suspended(self, queryset, name, value):
        """Filter organizations by suspension status using Organization.is_suspended."""
        if value is None:
            return queryset
        return queryset.filter(is_suspended=value)

    def filter_by_project_uuid(self, queryset, name, value):
        """
        Filter logic: When filtering by project UUID, return the organization
        containing that project and show all projects from that organization.
        """
        try:
            project = Project.objects.get(uuid=value)
            return queryset.filter(uuid=project.organization.uuid)
        except Project.DoesNotExist:
            raise NotFound(_("Project {} does not exist").format(value))
        except DjangoValidationError:
            raise NotFound(_("Invalid project UUID"))

    def filter_has_vtex_account(self, queryset, name, value):
        """
        Filter organizations based on whether they have projects with vtex_account
        true: organizations with at least one project having vtex_account
        false: organizations with no projects having vtex_account
        """
        if value is True:
            return queryset.filter(
                project__vtex_account__isnull=False, project__vtex_account__gt=""
            ).distinct()
        elif value is False:
            organizations_with_vtex = (
                Organization.objects.filter(
                    project__vtex_account__isnull=False, project__vtex_account__gt=""
                )
                .distinct()
                .values_list("uuid", flat=True)
            )
            return queryset.exclude(uuid__in=organizations_with_vtex)

        return queryset
