import pendulum
from rest_framework import mixins, status, exceptions
from rest_framework.decorators import action
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from drf_yasg2.utils import swagger_auto_schema
from django.utils.translation import ugettext_lazy as _
from django.shortcuts import get_object_or_404

from connect.common.models import (
    Organization,
    OrganizationAuthorization,
    OrganizationRole,
    BillingPlan,
)
from connect.api.v1.organization.permissions import (
    Has2FA,
    OrganizationHasPermission,
    IsCRMUser,
    _is_orm_user,
)
from connect.api.v2.paginations import CustomCursorPagination
from connect.api.v2.organizations.serializers import (
    OrganizationSeralizer,
    NestedAuthorizationOrganizationSerializer,
)
from connect.api.v2.projects.serializers import ProjectSerializer
from connect.api.v2.organizations.api_schemas import (
    create_organization_schema,
)


class OrganizationViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):

    queryset = Organization.objects.all()
    serializer_class = OrganizationSeralizer
    lookup_field = "uuid"
    permission_classes = [
        IsAuthenticated,
        OrganizationHasPermission | IsCRMUser,
        Has2FA,
    ]
    pagination_class = CustomCursorPagination

    def get_queryset(self, *args, **kwargs):
        if getattr(self, "swagger_fake_view", False):
            return Organization.objects.none()  # pragma: no cover

        exclude_roles = [OrganizationRole.NOT_SETTED.value]
        auth = (
            OrganizationAuthorization.objects.exclude(role__in=exclude_roles)
            .filter(user=self.request.user)
            .values("organization")
        )

        return self.queryset.filter(pk__in=auth)

    def get_object(self):
        if _is_orm_user(self.request.user):
            return get_object_or_404(Organization, uuid=self.kwargs["uuid"])
        return super().get_object()

    def get_ordering(self):
        valid_fields = (
            org_fields.name for org_fields in Organization._meta.get_fields()
        )
        ordering = []
        for param in self.request.query_params.getlist("ordering"):
            if param.startswith("-"):
                field = param[1:]
            else:
                field = param
            if field in valid_fields:
                ordering.append(param)
        return ordering or ["created_at"]

    @swagger_auto_schema(request_body=create_organization_schema)
    def create(self, request, *args, **kwargs):
        org_data = request.data.get("organization")
        project_data = request.data.get("project")

        # Organization
        serializer = self.get_serializer(data=org_data)

        try:
            serializer.is_valid(raise_exception=True)
        except exceptions.ValidationError as e:
            raise exceptions.ValidationError(
                {"organization": e.detail}, code=e.get_codes()
            )

        instance = serializer.save()

        if type(instance) == dict:
            return Response(**instance)

        # Project
        project_data.update({"organization": instance.uuid})
        project_serializer = ProjectSerializer(
            data=project_data, context={"request": request}
        )

        try:
            project_serializer.is_valid(raise_exception=True)
        except exceptions.ValidationError as e:
            raise exceptions.ValidationError({"project": e.detail}, code=e.get_codes())

        project_instance = project_serializer.save()

        if type(project_instance) == dict:
            instance.delete()
            return Response(**project_instance)

        data = {"organization": serializer.data, "project": project_serializer.data}

        return Response(data, status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        # TODO implement soft delete for organization
        user_email = self.request.user.email
        instance.perform_destroy_ai_organization(user_email)
        instance.delete()

    @action(
        detail=True,
        methods=["GET"],
        url_name="get-contact-active",
    )
    def get_contact_active(self, request, **kwargs):  # pragma: no cover
        organization = self.get_object()

        before = request.query_params.get("before")
        after = request.query_params.get("after")

        if not before or not after:
            raise ValidationError(
                _("Need to pass 'before' and 'after' in query params")
            )

        before = pendulum.parse(before, strict=False).end_of("day")
        after = pendulum.parse(after, strict=False).start_of("day")

        result = {"projects": []}

        for project in organization.project.all():
            result["projects"].append(
                {
                    "uuid": project.uuid,
                    "name": project.name,
                    "plan": project.organization.organization_billing.plan,
                    "plan_method": project.organization.organization_billing.plan_method,
                    "flow_organization": project.flow_organization,
                    "active_contacts": project.get_contacts(
                        before=str(before),
                        after=str(after),
                        counting_method=BillingPlan.ACTIVE_CONTACTS,
                    ),
                    "attendances": project.get_contacts(
                        before=str(before),
                        after=str(after),
                        counting_method=BillingPlan.ATTENDANCES,
                    ),
                }
            )

        return Response(data=result, status=status.HTTP_200_OK)


class OrganizationAuthorizationViewSet(
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    queryset = Organization.objects
    permission_classes = [IsAuthenticated, OrganizationHasPermission]
    lookup_field = "uuid"

    def get_serializer_class(self):
        return NestedAuthorizationOrganizationSerializer
