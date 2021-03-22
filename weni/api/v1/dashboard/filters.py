from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import ugettext_lazy as _
from django_filters import rest_framework as filters
from rest_framework.exceptions import NotFound
from rest_framework.exceptions import PermissionDenied

from weni.common.models import Project, ServiceStatus


class StatusServiceFilter(filters.FilterSet):
    class Meta:
        model = ServiceStatus
        fields = ["project_uuid"]

    project_uuid = filters.UUIDFilter(
        field_name="project_uuid",
        required=True,
        method="filter_project_uuid",
        help_text=_("Project's UUID"),
    )

    def filter_project_uuid(self, queryset, name, value):
        request = self.request
        try:
            project = Project.objects.get(uuid=value)
            authorization = project.organization.get_user_authorization(request.user)
            if not authorization.can_read:
                raise PermissionDenied()
            return queryset.filter(project__uuid=value)
        except Project.DoesNotExist:
            raise NotFound(_("Project {} does not exist").format(value))
        except DjangoValidationError:
            raise NotFound(_("Invalid project UUID"))
