from django.conf import settings
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.http import JsonResponse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status
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
    RequestPermissionOrganization, GenericBillingData,
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

        return JsonResponse(data=setup_intent, status=status.HTTP_200_OK)

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

        return JsonResponse(data={"status": True}, status=status.HTTP_200_OK)

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

        if organization.organization_billing.remove_credit_card:

            organization.is_suspended = True
            organization.save(update_fields=["is_suspended"])

            return JsonResponse(data={"status": True}, status=status.HTTP_200_OK)
        return JsonResponse(data={"status": False}, status=status.HTTP_304_NOT_MODIFIED)

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

        return JsonResponse(data=result, status=status.HTTP_200_OK)

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
        return JsonResponse(data=response, status=status.HTTP_200_OK)

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
        st = status.HTTP_200_OK
        result = {"active-contacts": {"organization_active_contacts": organization.active_contacts}}
        return JsonResponse(data=result, status=st)

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
        customer = organization.organization_billing.get_stripe_customer
        return JsonResponse(data=StripeGateway().get_card_data(customer.id), status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["PATCH"],
        url_name="billing-closing-plan",
        url_path="billing/closing-plan/(?P<organization_uuid>[^/.]+)",
        authentication_classes=[ExternalAuthentication],
        permission_classes=[AllowAny],
    )
    def closing_plan(self, request, organization_uuid):  # pragma: no cover
        result = {}
        organization = get_object_or_404(Organization, uuid=organization_uuid)

        org_billing = organization.organization_billing
        org_billing.termination_date = timezone.now().date()
        org_billing.is_active = False
        org_billing.save()
        # suspends the organization's projects
        for project in organization.project.all():
            celery_app.send_task(
                "update_suspend_project",
                args=[
                    str(project.flow_organization),
                    True
                ],
            )
        result = {
            "plan": org_billing.plan,
            "is_active": org_billing.is_active,
            "termination_date": org_billing.termination_date,
        }
        return JsonResponse(data=result, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["PATCH"],
        url_name="billing-reactivate-plan",
        url_path="billing/reactivate-plan/(?P<organization_uuid>[^/.]+)",
        authentication_classes=[ExternalAuthentication],
        permission_classes=[AllowAny],
    )
    def reactivate_plan(self, request, organization_uuid):  # pragma: no cover
        result = {}

        organization = get_object_or_404(Organization, uuid=organization_uuid)
        org_billing = organization.organization_billing
        org_billing.termination_date = None
        org_billing.is_active = True
        org_billing.save()

        for project in organization.project.all():
            celery_app.send_task(
                "update_suspend_project",
                args=[
                    str(project.flow_organization),
                    False
                ],
            )
        result = {
            "plan": org_billing.plan,
            "is_active": org_billing.is_active,
            "termination_date": org_billing.termination_date,
        }
        return JsonResponse(data=result, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["PATCH"],
        url_name="billing-change-plan",
        url_path="billing/change-plan/(?P<organization_uuid>[^/.]+)",
        authentication_classes=[ExternalAuthentication],
        permission_classes=[AllowAny],
    )
    def change_plan(self, request, organization_uuid):
        plan = request.data.get("organization_billing_plan")
        organization = get_object_or_404(Organization, uuid=organization_uuid)
        org_billing = organization.organization_billing
        change_plan = org_billing.change_plan(plan)
        if change_plan:
            return JsonResponse(data={"plan": org_billing.plan}, status=status.HTTP_200_OK)
        return JsonResponse(data={"message": "Invalid plan choice"}, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=["GET"],
        url_name='organization-on-limit',
        url_path='billing/organization-on-limit/(?P<organization_uuid>[^/.]+)',
        authentication_classes=[ExternalAuthentication],
        permission_classes=[AllowAny],
    )
    def organization_on_limit(self, request, organization_uuid):
        organization = get_object_or_404(Organization, uuid=organization_uuid)
        self.check_object_permissions(self.request, organization)
        limits = GenericBillingData.objects.first() if GenericBillingData.objects.all().exists() else GenericBillingData.objects.create()
        billing = organization.organization_billing
        current_active_contacts = organization.active_contacts

        response = {}
        st = status.HTTP_200_OK

        if billing.plan == billing.PLAN_FREE:
            if limits.free_active_contacts_limit >= current_active_contacts:
                response = {
                    'status': 'OK',
                    'message': 'free plan is valid yet',
                    'missing_quantity': limits.free_active_contacts_limit - current_active_contacts,
                    'limit': limits.free_active_contacts_limit,
                }
            else:
                response = {
                    'status': "FAIL",
                    'message': "free plan isn't longer valid",
                    'excess_quantity': current_active_contacts - limits.free_active_contacts_limit,
                    'limit': limits.free_active_contacts_limit,
                }
                st = status.HTTP_402_PAYMENT_REQUIRED
        else:
            response = {
                'status': 'OK',
                'message': "Your plan don't have a contact active limit"
            }
        return JsonResponse(data=response, status=st)

    @action(
        detail=True,
        methods=["GET", "PATCH"],
        url_name="active-contacts-limit",
        url_path="billing/active-contacts-limit",
        authentication_classes=[ExternalAuthentication],
        permission_classes=[AllowAny],
    )
    def active_contacts_limit(self, request):  # pragma: no cover
        limit = GenericBillingData.objects.first() if GenericBillingData.objects.all().exists() else GenericBillingData.objects.create()
        response = {
            "active_contacts_limit": limit.free_active_contacts_limit
        }
        if request.method == 'PATCH':
            new_limit = request.data.get("active_contacts_limit")
            limit.free_active_contacts_limit = new_limit
            response = {
                "active_contacts_limit": limit.free_active_contacts_limit
            }
        return JsonResponse(data=response, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["POST"],
        url_name='additional-billing-information',
        url_path='billing/add-additional-information/(?P<organization_uuid>[^/.]+)',
        authentication_classes=[ExternalAuthentication],
        permission_classes=[AllowAny]
    )
    def add_additional_billing_information(self, request, organization_uuid):
        organization = get_object_or_404(Organization, uuid=organization_uuid)
        cpf = request.data.get('cpf') if 'cpf' in request.data else None
        cnpj = request.data.get('cnpj') if 'cnpj' in request.data else None
        additional_info = request.data.get('additional_billing_info') if 'additional_billing_info' in request.data else None
        response = [
            {
                'status': 'SUCESS',
                'response': {
                    'CPF': cpf,
                    'CNPJ': cnpj,
                    'additional_information': additional_info
                }
            },
            {
                'status': 'NO CHANGES',
                'message': _('No changes received')
            }
        ]
        billing = organization.organization_billing
        result = billing.add_additional_information(
            {
                'additional_info': additional_info,
                'cpf': cpf,
                'cnpj': cnpj
            }
        )
        return JsonResponse(data=response[result], status=status.HTTP_200_OK)


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
