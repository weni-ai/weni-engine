from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.http import JsonResponse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from connect import utils
from connect.api.v1.metadata import Metadata
from connect.api.v1.mixins import MultipleFieldLookupMixin
from connect.api.v1.organization.filters import (
    OrganizationAuthorizationFilter,
    RequestPermissionOrganizationFilter,
)
from connect.api.v1.organization.permissions import (
    OrganizationHasPermission,
    OrganizationAdminManagerAuthorization,
)
from connect.api.v1.organization.serializers import (
    OrganizationSeralizer,
    OrganizationAuthorizationSerializer,
    OrganizationAuthorizationRoleSerializer,
    RequestPermissionOrganizationSerializer,
)
from connect.authentication.models import User
from connect.celery import app as celery_app
from connect.common.models import (
    Organization,
    OrganizationAuthorization,
    RequestPermissionOrganization,
)
from connect.middleware import ExternalAuthentication

from connect.billing.gateways.stripe_gateway import StripeGateway


class OrganizationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSeralizer
    permission_classes = [IsAuthenticated, OrganizationHasPermission]
    lookup_field = "uuid"
    metadata_class = Metadata

    def get_queryset(self, *args, **kwargs):
        if getattr(self, "swagger_fake_view", False):
            # queryset just for schema generation metadata
            return Organization.objects.none()  # pragma: no cover
        auth = (
            OrganizationAuthorization.objects.exclude(role=0)
            .filter(user=self.request.user)
            .values("organization")
        )
        return self.queryset.filter(pk__in=auth)

    def perform_destroy(self, instance):
        inteligence_organization = instance.inteligence_organization
        instance.delete()

        celery_app.send_task(
            "delete_organization",
            args=[inteligence_organization, self.request.user.email],
        )

    @action(
        detail=True,
        methods=["GET"],
        url_name="invoice-setup-intent",
        url_path="invoice/setup_intent/(?P<organization_uuid>[^/.]+)",
    )
    def setup_intent(self, request, organization_uuid, **kwargs):  # pragma: no cover
        import stripe

        organization = get_object_or_404(Organization, uuid=organization_uuid)

        self.check_object_permissions(self.request, organization)

        stripe.api_key = settings.BILLING_SETTINGS.get("stripe", {}).get("API_KEY")
        setup_intent = stripe.SetupIntent.create(
            customer=organization.organization_billing.get_stripe_customer.id
        )

        return JsonResponse(data=setup_intent)

    @action(
        detail=True,
        methods=["GET"],
        url_name="invoice-setup-intent",
        url_path="retry-capture-payment/(?P<organization_uuid>[^/.]+)",
    )
    def retry_capture_payment(
        self, request, organization_uuid, **kwargs
    ):  # pragma: no cover
        organization = get_object_or_404(Organization, uuid=organization_uuid)

        self.check_object_permissions(self.request, organization)

        organization.organization_billing.allow_payments()

        return JsonResponse(data={"status": True})

    @action(
        detail=True,
        methods=["GET"],
        url_name="remove-card-setup",
        url_path="remove-card-setup/(?P<organization_uuid>[^/.]+)",
    )
    def remove_card_setup(
        self, request, organization_uuid, **kwargs
    ):  # pragma: no cover
        organization = get_object_or_404(Organization, uuid=organization_uuid)

        self.check_object_permissions(self.request, organization)

        organization.organization_billing.remove_credit_card()

        organization.is_suspended = True
        organization.save(update_fields=["is_suspended"])

        return JsonResponse(data={"status": True})

    @action(
        detail=True,
        methods=["GET"],
        url_name="get-contact-active",
        url_path="grpc/contact-active/(?P<organization_uuid>[^/.]+)",
        authentication_classes=[ExternalAuthentication],
        permission_classes=[AllowAny],
    )
    def get_contact_active(
            self, request, organization_uuid, **kwargs
    ):  # pragma: no cover

        organization = get_object_or_404(Organization, uuid=organization_uuid)

        self.check_object_permissions(self.request, organization)

        before = str(request.query_params.get("before") + " 00:00")
        after = str(request.query_params.get("after") + " 00:00")

        if not before or not after:
            raise ValidationError(
                _("Need to pass 'before' and 'after' in query params")
            )

        flow_instance = utils.get_grpc_types().get("flow")

        result = {"projects": []}

        for project in organization.project.all():
            contact_count = flow_instance.get_billing_total_statistics(
                project_uuid=str(project.flow_organization),
                before=before,
                after=after,
            ).get("active_contacts")

            result["projects"].append(
                {
                    "uuid": project.uuid,
                    "name": project.name,
                    "flow_organization": project.flow_organization,
                    "active_contacts": contact_count,
                }
            )

        return JsonResponse(data=result)

    @action(
        detail=True,
        methods=["GET"],
        url_name="get-contact-active-per-project",
        url_path="contact-active-per-project/(?P<organization_uuid>[^/.]+)",
        authentication_classes=[ExternalAuthentication],
        permission_classes=[AllowAny],
    )
    def get_contacts_active_per_project(self, request, organization_uuid):
        org = get_object_or_404(Organization, uuid=organization_uuid)
        self.check_object_permissions(self.request, org)
        response = {"projects": []}
        for project in org.project.all():
            response["projects"].append(
                {
                    'project_uuid': project.uuid,
                    'project_name': project.name,
                    "active_contacts": project.contact_count
                }
            )
        return JsonResponse(data=response)

    @action(
        detail=True,
        methods=["GET"],
        url_name="get-org-active-contacts",
        authentication_classes=[ExternalAuthentication],
        url_path="org-active-contacts/(?P<organization_uuid>[^/.]+)",
        permission_classes=[AllowAny],
    )
    def get_active_org_contacts(self, request, organization_uuid):
        organization = get_object_or_404(Organization, uuid=organization_uuid)
        self.check_object_permissions(self.request, organization)

        contact_count = 0
        result = {"active-contacts": {}}

        for project in organization.project.all():
            contact_count += project.contact_count
        result["active-contacts"] = {
            "organization_active_contacts": contact_count,
        }
        return JsonResponse(data=result)

    @action(
        detail=True,
        methods=["GET"],
        url_name='get-stripe-card-data',
        url_path='get-stripe-card-data/(?P<organization_uuid>[^/.]+)',
        authentication_classes=[ExternalAuthentication],
        permission_classes=[AllowAny],
    )
    def get_stripe_card_data(self, request, organization_uuid):
        if not organization_uuid:
            raise ValidationError(
                _("Need to pass 'organization_uuid'")
            )
        organization = get_object_or_404(Organization, uuid=organization_uuid)
        self.check_object_permissions(self.request, organization)
        costomer = organization.organization_billing.get_stripe_customer
        return JsonResponse(data=StripeGateway().get_card_data(costomer.id))


class OrganizationAuthorizationViewSet(
    MultipleFieldLookupMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    queryset = OrganizationAuthorization.objects
    serializer_class = OrganizationAuthorizationSerializer
    filter_class = OrganizationAuthorizationFilter
    lookup_fields = ["organization__uuid", "user__id"]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = [
        "=user__first_name",
        "^user__first_name",
        "$user__first_name",
        "=user__last_name",
        "^user__last_name",
        "$user__last_name",
        "=user__last_name",
        "^user__username",
        "$user__username",
        "=user__email",
        "^user__email",
        "$user__email",
    ]
    ordering = ["-user__first_name"]

    permission_classes = [IsAuthenticated]

    def get_object(self):
        organization_uuid = self.kwargs.get("organization__uuid")
        user_id = self.kwargs.get("user__id")

        organization = get_object_or_404(Organization, uuid=organization_uuid)
        user = get_object_or_404(User, pk=user_id)
        obj = organization.get_user_authorization(user)

        self.check_object_permissions(self.request, obj)
        return obj

    def update(self, *args, **kwargs):
        self.lookup_field = "user__id"

        self.filter_class = None
        self.serializer_class = OrganizationAuthorizationRoleSerializer
        self.permission_classes = [
            IsAuthenticated,
            OrganizationAdminManagerAuthorization,
        ]
        response = super().update(*args, **kwargs)
        instance = self.get_object()
        instance.send_new_role_email(self.request.user)
        return response

    def list(self, request, *args, **kwargs):
        self.lookup_fields = []
        return super().list(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self.permission_classes = [
            IsAuthenticated,
            OrganizationAdminManagerAuthorization,
        ]
        self.filter_class = None
        self.lookup_field = "user__id"
        return super().destroy(request, *args, **kwargs)

    @action(
        detail=True,
        methods=["DELETE"],
        url_name="organization-remove-my-user",
        lookup_fields=["organization__uuid", "user__username"],
    )
    def remove_my_user(self, request, **kwargs):  # pragma: no cover
        """
        Delete my user authorization
        """
        organization_uuid = self.kwargs.get("organization__uuid")

        organization = get_object_or_404(Organization, uuid=organization_uuid)
        obj = organization.get_user_authorization(self.request.user)

        self.check_object_permissions(self.request, obj)

        obj.delete()
        return Response(status=204)


class RequestPermissionOrganizationViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    queryset = RequestPermissionOrganization.objects
    serializer_class = RequestPermissionOrganizationSerializer
    permission_classes = [IsAuthenticated, OrganizationAdminManagerAuthorization]
    filter_class = RequestPermissionOrganizationFilter
    metadata_class = Metadata
