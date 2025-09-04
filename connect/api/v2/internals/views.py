import json

from rest_framework import views, mixins
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from connect.common.models import Organization, Project, BillingPlan
from connect.api.v2.internals.serializers import (
    OrganizationAISerializer,
    CustomParameterSerializer,
    InternalProjectSerializer,
    CRMOrganizationSerializer,
)
from connect.api.v2.internals.filters import CRMOrganizationFilter
from connect.api.v1.internal.permissions import ModuleHasPermission
from connect.api.v1.organization.permissions import IsCRMUser
from connect.api.v2.paginations import CustomCursorPagination

from django.shortcuts import get_object_or_404

from drf_yasg2.utils import swagger_auto_schema
from rest_framework.viewsets import ModelViewSet


class InternalProjectViewSet(ModelViewSet):
    permission_classes = [ModuleHasPermission]
    queryset = Project.objects.all()
    lookup_field = "uuid"
    serializer_class = InternalProjectSerializer


class AIGetOrganizationView(views.APIView):
    permission_classes = [ModuleHasPermission]

    @swagger_auto_schema(
        operation_description="GET /v2/internals/connect/organizations?project_uuid={uuid}",
        query_serializer=CustomParameterSerializer,
    )
    def get(self, request, **kwargs):
        """Get organization data using proejct_uuid"""

        uuid = request.query_params.get("project_uuid")
        organization = get_object_or_404(Organization, project__uuid=uuid)
        serializer = OrganizationAISerializer(organization)

        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="PATCH /v2/internals/connect/organizations?project_uuid={uuid}",
        query_serializer=CustomParameterSerializer,
    )
    def patch(self, request, **kwargs):
        uuid = request.query_params.get("project_uuid")
        if type(request.data) == str:
            data = json.loads(request.data)
            intelligence_organization = data.get("intelligence_organization")
        else:
            intelligence_organization = request.data.get("intelligence_organization")

        organization = get_object_or_404(Organization, project__uuid=uuid)
        organization.inteligence_organization = int(intelligence_organization)
        organization.save(update_fields=["inteligence_organization"])

        response = {
            "organization": {
                "intellgence_organization": organization.inteligence_organization,
                "uuid": organization.uuid,
            }
        }

        return Response(response)


class CRMOrganizationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    """
    ViewSet for CRM users to retrieve detailed organization information
    with comprehensive data including users and projects.
    """

    queryset = Organization.objects.all()
    serializer_class = CRMOrganizationSerializer
    permission_classes = [IsAuthenticated, IsCRMUser | ModuleHasPermission]
    pagination_class = CustomCursorPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = CRMOrganizationFilter
    lookup_field = "uuid"

    def get_queryset(self):
        """Apply base filters"""
        if getattr(self, "swagger_fake_view", False):
            return Organization.objects.none()  # pragma: no cover

        queryset = super().get_queryset()

        queryset = queryset.select_related().prefetch_related(
            "authorizations__user", "project"
        )

        return queryset

    def get_ordering(self):
        """Support ordering by valid fields, default to created_at"""
        valid_fields = (field.name for field in Organization._meta.get_fields())
        ordering = []

        for param in self.request.query_params.getlist("ordering"):
            if param.startswith("-"):
                field = param[1:]
            else:
                field = param
            if field in valid_fields:
                ordering.append(param)

        return ordering or ["created_at"]

    @swagger_auto_schema(
        operation_description="List organizations for CRM users with filtering",
        tags=["CRM Organizations"],
    )
    def list(self, request, *args, **kwargs):
        """List organizations with filtering capabilities for CRM users"""
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Retrieve specific organization details",
        tags=["CRM Organizations"],
    )
    def retrieve(self, request, *args, **kwargs):
        """Retrieve a specific organization by UUID"""
        return super().retrieve(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="trial-extension")
    def trial_extension(self, request, *args, **kwargs):
        """QA helper endpoint for trial extension flows (CRM users only).

        Body expects {"action": "enable|force_end_first|force_end_extension|set_first_end|set_extension_end|status", "date": "YYYY-MM-DD"}
        """
        organization: Organization = self.get_object()
        billing: BillingPlan = organization.organization_billing

        op = request.data.get("action")
        date_str = request.data.get("date")

        def status_payload():
            return {
                "plan": billing.plan,
                "is_active": billing.is_active,
                "trial_end_date": billing.trial_end_date,
                "trial_extension_enabled": billing.trial_extension_enabled,
                "trial_extension_end_date": billing.trial_extension_end_date,
                "org_is_suspended": organization.is_suspended,
            }

        if op == "status":
            return Response(status_payload())

        if op == "enable":
            if billing.enable_trial_extension():
                return Response(status_payload())
            return Response({"detail": "Not eligible to enable trial extension."}, status=400)

        if op == "force_end_first" or op == "force_end_extension":
            billing.end_trial_period()
            billing.send_email_trial_plan_expired_due_time_limit()
            return Response(status_payload())

        if op == "set_first_end":
            if billing.plan != BillingPlan.PLAN_TRIAL:
                return Response({"detail": "Plan must be trial."}, status=400)
            if not date_str:
                return Response({"detail": "Missing 'date' (YYYY-MM-DD)."}, status=400)
            import pendulum

            try:
                billing.trial_end_date = pendulum.parse(date_str).end_of("day")
                billing.save(update_fields=["trial_end_date"])
                return Response(status_payload())
            except Exception:
                return Response({"detail": "Invalid 'date' format."}, status=400)

        if op == "set_extension_end":
            if not billing.trial_extension_enabled:
                return Response({"detail": "Trial extension is not enabled."}, status=400)
            if not date_str:
                return Response({"detail": "Missing 'date' (YYYY-MM-DD)."}, status=400)
            import pendulum

            try:
                billing.trial_extension_end_date = pendulum.parse(date_str).end_of("day")
                billing.save(update_fields=["trial_extension_end_date"])
                return Response(status_payload())
            except Exception:
                return Response({"detail": "Invalid 'date' format."}, status=400)

        return Response({"detail": "Invalid action."}, status=400)
