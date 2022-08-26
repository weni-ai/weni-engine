from random import randint
import uuid
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
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from connect.api.v1.metadata import Metadata
from connect.api.v1.mixins import MultipleFieldLookupMixin
from connect.api.v1.organization.filters import (
    OrganizationAuthorizationFilter,
    RequestPermissionOrganizationFilter,
)
from connect.api.v1.organization.permissions import (
    Has2FA,
    OrganizationHasPermission,
    OrganizationAdminManagerAuthorization,
)
from connect.api.v1.organization.serializers import (
    OrganizationSeralizer,
    OrganizationAuthorizationSerializer,
    OrganizationAuthorizationRoleSerializer,
    RequestPermissionOrganizationSerializer,
)
from ..project.serializers import ProjectSerializer, TemplateProjectSerializer

from connect.authentication.models import User
from connect.celery import app as celery_app
from connect.common.models import (
    Organization,
    OrganizationAuthorization,
    RequestPermissionOrganization,
    GenericBillingData,
    OrganizationRole,
    ProjectRole,
    BillingPlan,
    Project,
)
from connect import billing
from connect.billing.gateways.stripe_gateway import StripeGateway
from connect.utils import count_contacts
from connect.api.v1.internal.intelligence.intelligence_rest_client import IntelligenceRESTClient
import pendulum
from connect.common import tasks
import logging


logger = logging.getLogger(__name__)


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
    permission_classes = [IsAuthenticated, OrganizationHasPermission, Has2FA]
    lookup_field = "uuid"
    metadata_class = Metadata

    def get_queryset(self, *args, **kwargs):
        if getattr(self, "swagger_fake_view", False):
            # queryset just for schema generation metadata
            return Organization.objects.none()  # pragma: no cover
        exclude_roles = [OrganizationRole.NOT_SETTED.value]
        auth = (
            OrganizationAuthorization.objects.exclude(role__in=exclude_roles)
            .filter(user=self.request.user)
            .values("organization")
        )
        return self.queryset.filter(pk__in=auth)

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(
            self.filter_queryset(self.get_queryset().order_by("name")),
        )
        organization_serializer = OrganizationSeralizer(page, many=True, context=self.get_serializer_context())
        return self.get_paginated_response(organization_serializer.data)

    def create(self, request, *args, **kwargs):
        data = {}
        org_info = request.data.get("organization")
        project_info = request.data.get("project")
        user = request.user

        if not settings.TESTING:
            ai_client = IntelligenceRESTClient()
            ai_org = ai_client.create_organization(
                user_email=user.email,
                organization_name=org_info.get("name")
            )
            org_info.update(
                dict(
                    intelligence_organization=ai_org.get("id", 0)
                )
            )

        cycle = BillingPlan._meta.get_field(
            "cycle"
        ).default

        new_organization = Organization.objects.create(
            name=org_info.get("name"),
            description=org_info.get("description"),
            organization_billing__plan=org_info.get("plan"),
            organization_billing__cycle=cycle,
            inteligence_organization=org_info.get("intelligence_organization", 0)
        )

        if not settings.TESTING:
            try:
                if project_info.get("template"):
                    flows_info = tasks.create_template_project.delay(
                        project_info.get("name"),
                        user.email,
                        project_info.get("timezone")
                    )
                else:
                    flows_info = tasks.create_project.delay(
                        project_name=project_info.get("name"),
                        user_email=user.email,
                        project_timezone=project_info.get("timezone")
                    )

                flows_info.wait()
                flows_info = flows_info.result
            except Exception as error:
                data.update({
                    "message": "Could not create project",
                    "status": "FAILED"
                })
                logger.error(error)
                new_organization.delete()
                return Response(data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            flows_info = {
                "id": randint(1, 100),
                "uuid": uuid.uuid4()
            }

        project = Project.objects.create(
            name=project_info.get("name"),
            flow_id=flows_info.get("id"),
            flow_organization=flows_info.get("uuid"),
            organization=new_organization,
            is_template=True if project_info.get("template") else False
        )

        if project_info.get("template"):
            data = {
                "project": project,
                "organization": new_organization
            }
            project_data = TemplateProjectSerializer().create(data, request)
            if project_data.get("status") == "FAILED":
                new_organization.delete()
                project.delete()
                return Response(project_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        RequestPermissionOrganization.objects.create(
            email=user.email,
            organization=new_organization,
            role=OrganizationRole.ADMIN.value,
            created_by=user
        )

        for auth in org_info.get("authorizations", []):
            RequestPermissionOrganization.objects.create(
                email=auth.get("user_email"),
                organization=new_organization,
                role=auth.get("role"),
                created_by=user
            )
        serializer = OrganizationSeralizer(new_organization, context={"request": request})
        project_serializer = ProjectSerializer(project, context={"request": request})
        response_data = dict(
            project=project_serializer.data,
            status="SUCCESS",
            message="",
            organization=serializer.data
        )

        return Response(response_data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        intelligence_organization = instance.inteligence_organization
        instance.delete()
        ai_client = IntelligenceRESTClient()
        ai_client.delete_organization(organization_id=intelligence_organization, user_email=self.request.user.email)

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

        if (
            organization.organization_billing.plan
            != organization.organization_billing.PLAN_CUSTOM
            and organization.organization_billing.remove_credit_card
        ):
            organization.is_suspended = True
            organization.organization_billing.is_active = False
            organization.organization_billing.save(update_fields=["is_active"])
            organization.save(update_fields=["is_suspended"])
            user_name = (
                organization.name if request.user is None else request.user.first_name
            )
            organization.organization_billing.send_email_removed_credit_card(
                user_name,
                organization.authorizations.values_list("user__email", flat=True),
            )

            return JsonResponse(data={"status": True}, status=status.HTTP_200_OK)
        return JsonResponse(data={"status": False}, status=status.HTTP_304_NOT_MODIFIED)

    @action(
        detail=True,
        methods=["GET"],
        url_name="get-contact-active",
        url_path="grpc/contact-active/(?P<organization_uuid>[^/.]+)",
    )
    def get_contact_active(
        self, request, organization_uuid, **kwargs
    ):  # pragma: no cover

        organization = get_object_or_404(Organization, uuid=organization_uuid)

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
                    "flow_organization": project.flow_organization,
                    "active_contacts": count_contacts(project=project, before=before, after=after),
                }
            )

        return JsonResponse(data=result, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["GET"],
        url_name="get-contact-active-per-project",
        url_path="contact-active-per-project/(?P<organization_uuid>[^/.]+)",
    )
    def get_contacts_active_per_project(self, request, organization_uuid):
        org = get_object_or_404(Organization, uuid=organization_uuid)
        self.check_object_permissions(self.request, org)
        response = {"projects": []}
        for project in org.project.all():
            response["projects"].append(
                {
                    "project_uuid": project.uuid,
                    "project_name": project.name,
                    "active_contacts": project.contact_count,
                }
            )
        return JsonResponse(data=response, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["GET"],
        url_name="get-org-active-contacts",
        url_path="org-active-contacts/(?P<organization_uuid>[^/.]+)",
    )
    def get_active_org_contacts(self, request, organization_uuid):
        organization = get_object_or_404(Organization, uuid=organization_uuid)
        self.check_object_permissions(self.request, organization)
        st = status.HTTP_200_OK
        result = {
            "active-contacts": {
                "organization_active_contacts": organization.active_contacts
            }
        }
        return JsonResponse(data=result, status=st)

    @action(
        detail=True,
        methods=["GET"],
        url_name="get-stripe-card-data",
        url_path="get-stripe-card-data/(?P<organization_uuid>[^/.]+)",
    )
    def get_stripe_card_data(self, request, organization_uuid):
        if not organization_uuid:
            raise ValidationError(_("Need to pass 'organization_uuid'"))
        organization = get_object_or_404(Organization, uuid=organization_uuid)
        self.check_object_permissions(self.request, organization)
        customer = organization.organization_billing.get_stripe_customer
        return JsonResponse(
            data=StripeGateway().get_card_data(customer.id), status=status.HTTP_200_OK
        )

    @action(
        detail=True,
        methods=["PATCH"],
        url_name="billing-closing-plan",
        url_path="billing/closing-plan/(?P<organization_uuid>[^/.]+)",
    )
    def closing_plan(self, request, organization_uuid):  # pragma: no cover
        result = {}
        organization = get_object_or_404(Organization, uuid=organization_uuid)
        self.check_object_permissions(self.request, organization)

        org_billing = organization.organization_billing
        org_billing.termination_date = timezone.now().date()
        org_billing.is_active = False
        org_billing.save()
        # suspends the organization's projects
        for project in organization.project.all():
            celery_app.send_task(
                "update_suspend_project",
                args=[str(project.flow_organization), True],
            )
        user_name = (
            org_billing.organization.name
            if request.user is None
            else request.user.first_name
        )
        org_billing.send_email_finished_plan(
            user_name, organization.authorizations.values_list("user__email", flat=True)
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
    )
    def reactivate_plan(self, request, organization_uuid):  # pragma: no cover

        organization = get_object_or_404(Organization, uuid=organization_uuid)
        self.check_object_permissions(self.request, organization)

        org_billing = organization.organization_billing
        org_billing.termination_date = None
        org_billing.is_active = True
        org_billing.contract_on = timezone.now().date()
        org_billing.save()

        for project in organization.project.all():
            celery_app.send_task(
                "update_suspend_project",
                args=[str(project.flow_organization), False],
            )
        user_name = (
            org_billing.organization.name
            if request.user is None
            else request.user.first_name
        )
        org_billing.send_email_reactivated_plan(
            user_name, organization.authorizations.values_list("user__email", flat=True)
        )
        result = {
            "plan": org_billing.plan,
            "is_active": org_billing.is_active,
            "termination_date": org_billing.termination_date,
            "contract_on": org_billing.contract_on,
        }
        return JsonResponse(data=result, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["PATCH"],
        url_name="billing-change-plan",
        url_path="billing/change-plan/(?P<organization_uuid>[^/.]+)",
    )
    def change_plan(self, request, organization_uuid):
        plan = request.data.get("organization_billing_plan")
        organization = get_object_or_404(Organization, uuid=organization_uuid)
        self.check_object_permissions(self.request, organization)
        org_billing = organization.organization_billing
        old_plan = organization.organization_billing.plan
        change_plan = org_billing.change_plan(plan)
        if change_plan:
            organization.organization_billing.send_email_changed_plan(
                organization.name,
                organization.authorizations.values_list("user__email", flat=True),
                old_plan,
            )
            return JsonResponse(
                data={"plan": org_billing.plan}, status=status.HTTP_200_OK
            )
        return JsonResponse(
            data={"message": "Invalid plan choice"}, status=status.HTTP_400_BAD_REQUEST
        )

    @action(
        detail=True,
        methods=["GET"],
        url_name="organization-on-limit",
        url_path="billing/organization-on-limit/(?P<organization_uuid>[^/.]+)",
    )
    def organization_on_limit(self, request, organization_uuid):
        organization = get_object_or_404(Organization, uuid=organization_uuid)
        self.check_object_permissions(self.request, organization)
        limits = GenericBillingData.get_generic_billing_data_instance()
        billing = organization.organization_billing
        current_active_contacts = organization.active_contacts

        response = {}
        st = status.HTTP_200_OK

        if billing.plan == billing.PLAN_FREE:
            if limits.free_active_contacts_limit >= current_active_contacts:
                response = {
                    "status": "OK",
                    "message": "free plan is valid yet",
                    "missing_quantity": limits.free_active_contacts_limit
                    - current_active_contacts,
                    "limit": limits.free_active_contacts_limit,
                    "current_active_contacts": current_active_contacts,
                }
            else:
                response = {
                    "status": "FAIL",
                    "message": "free plan isn't longer valid",
                    "excess_quantity": current_active_contacts
                    - limits.free_active_contacts_limit,
                    "limit": limits.free_active_contacts_limit,
                    "current_active_contacts": current_active_contacts,
                }
        else:
            response = {
                "status": "OK",
                "message": "Your plan don't have a contact active limit",
                "current_active_contacts": current_active_contacts,
            }
        return JsonResponse(data=response, status=st)

    @action(
        detail=True,
        methods=["GET", "PATCH"],
        url_name="active-contacts-limit",
        url_path="billing/active-contacts-limit",
    )
    def active_contacts_limit(self, request):  # pragma: no cover
        limit = GenericBillingData.get_generic_billing_data_instance()
        response = {"active_contacts_limit": limit.free_active_contacts_limit}
        if request.method == "PATCH":
            new_limit = request.data.get("active_contacts_limit")
            limit.free_active_contacts_limit = new_limit
            response = {"active_contacts_limit": limit.free_active_contacts_limit}
        return JsonResponse(data=response, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["POST"],
        url_name="additional-billing-information",
        url_path="billing/add-additional-information/(?P<organization_uuid>[^/.]+)",
    )
    def add_additional_billing_information(self, request, organization_uuid):
        organization = get_object_or_404(Organization, uuid=organization_uuid)
        self.check_object_permissions(self.request, organization)
        personal_identification_number = (
            request.data.get("personal_identification_number")
            if "personal_identification_number" in request.data
            else None
        )
        extra_integration = (
            request.data.get("extra_integration")
            if "extra_integration" in request.data
            else None
        )
        additional_info = (
            request.data.get("additional_billing_info")
            if "additional_billing_info" in request.data
            else None
        )
        response = [
            {
                "status": "SUCCESS",
                "response": {
                    "personal_identification_number": personal_identification_number,
                    "additional_information": additional_info,
                    "extra_integration": extra_integration,
                },
            },
            {"status": "NO CHANGES", "message": _("No changes received")},
        ]
        billing = organization.organization_billing
        result = billing.add_additional_information(
            {
                "additional_info": additional_info,
                "personal_identification_number": personal_identification_number,
                "extra_integration": extra_integration,
            }
        )
        return JsonResponse(data=response[result], status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["GET"],
        url_name="billing-precification",
        url_path="billing/precification",
    )
    def get_billing_precification(self, request):
        billing_data = GenericBillingData.get_generic_billing_data_instance()
        return JsonResponse(data=billing_data.precification, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["GET"],
        url_name="extra-integrations",
        url_path="billing/extra-integrations/(?P<organization_uuid>[^/.]+)",
    )
    def get_extra_active_integrations(self, request, organization_uuid):
        organization = get_object_or_404(Organization, uuid=organization_uuid)
        self.check_object_permissions(self.request, organization)
        response = {
            "extra_active_integrations": organization.extra_active_integrations,
            "limit_extra_integrations": organization.extra_integration,
        }
        return JsonResponse(data=response, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["PATCH"],
        url_name="enforce-users-2fa",
        url_path="enforce-two-factor-auth/(?P<organization_uuid>[^/.]+)",
    )
    def set_2fa_required(self, request, organization_uuid):
        flag = request.data.get("2fa_required")
        organization = get_object_or_404(Organization, uuid=organization_uuid)
        organization.set_2fa_required(flag)
        data = {"2fa_required": organization.enforce_2fa}
        return JsonResponse(data=data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=['POST'],
        url_path="billing/validate-customer-card"

    )
    def validate_customer_card(self, request):
        customer = request.data.get("customer")
        if customer:
            gateway = billing.get_gateway("stripe")
            response = gateway.verify_payment_method(customer)
            response["charge"] = None

            if response["cvc_check"]:
                response["charge"] = gateway.card_verification_charge(customer)

            return JsonResponse(data=response, status=status.HTTP_200_OK)
        return JsonResponse(data={"response": "no customer"}, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=["POST"],
        url_name="organization-retrieve",
        url_path="internal/retrieve"
    )
    def retrieve_organization(self, request):
        flow_organization_uuid = request.uuid
        organization = Organization.objects.get(project__flow_organization=flow_organization_uuid)
        return {
            "status": status.HTTP_200_OK,
            "response": {
                "uuid": str(organization.uuid),
                "name": organization.name,
                "description": organization.description,
                "inteligence_organization": organization.inteligence_organization,
                "extra_integration": organization.extra_integration,
                "is_suspended": organization.is_suspended,
            }
        }


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

    def get_queryset(self, *args, **kwargs):
        if getattr(self, "swagger_fake_view", False):
            # queryset just for schema generation metadata
            return OrganizationAuthorization.objects.none()  # pragma: no cover
        exclude_roles = [ProjectRole.VIEWER.value, ProjectRole.NOT_SETTED.value]
        return self.queryset.exclude(role__in=exclude_roles)

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
